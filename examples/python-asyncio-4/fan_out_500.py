"""Interview drill: call 500 APIs, answer within 1 s, and never put more than 50 calls on the API."""

import asyncio
import contextlib

from sellers_load import LimitedSeller

CALLS, CAP, DEADLINE = 500, 50, 1.0


async def call(port, stats):
    async with stats["limit"]:
        stats["now"] += 1
        stats["peak"] = max(stats["peak"], stats["now"])
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            try:
                writer.write(b"item\n")
                await writer.drain()
                return await reader.readline()
            finally:
                writer.close()
                with contextlib.suppress(OSError):
                    await writer.wait_closed()
        finally:
            stats["now"] -= 1


async def one(port, deadline, stats):
    try:
        async with asyncio.timeout_at(deadline):  # covers the wait for a slot and the call
            return "answered" if await call(port, stats) else "failed"
    except TimeoutError:
        return "timed out"
    except OSError:
        return "failed"


async def call_all(port):
    loop = asyncio.get_running_loop()
    start = loop.time()
    stats = {"limit": asyncio.Semaphore(CAP), "now": 0, "peak": 0}
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(one(port, start + DEADLINE, stats)) for _ in range(CALLS)]
    outcome = [t.result() for t in tasks]
    ms = round((loop.time() - start) * 10) * 100
    counts = ", ".join(f"{k} {outcome.count(k)}" for k in ("answered", "timed out", "failed"))
    print(f"{counts} of {CALLS} in about {ms:,} ms; most in flight: {stats['peak']}")


async def main():
    for label, latency in (("healthy API, 40 ms per call", 40), ("slow API, 180 ms per call", 180)):
        print(f"-- {label}, 100 workers --")
        with LimitedSeller("api", latency, 0, workers=100).running() as port:
            await call_all(port)


if __name__ == "__main__":
    asyncio.run(main())

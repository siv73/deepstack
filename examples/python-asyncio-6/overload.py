"""Two bursts of 50 calls hit a seller that has 10 workers (150 ms per job, like seller-c).

Without a cap, calls the gateway already gave up on stay in the seller's queue and are
still worked on. With a cap of 10 and the deadline around the wait, they are never sent.
"""

import asyncio
import contextlib
import time

from sellers_load import LimitedSeller

BURST, WORKERS, BUDGET = 50, 10, 0.25


async def call(port):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(b"kettle-1l\n")
        await writer.drain()
        return await reader.readline()
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


async def one(port, deadline, limit):
    try:
        async with asyncio.timeout_at(deadline):
            if limit is None:
                return await call(port)
            async with limit:  # the wait for a slot is inside the deadline
                return await call(port)
    except TimeoutError:
        return None


async def burst(port, limit):
    deadline = asyncio.get_running_loop().time() + BUDGET
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(one(port, deadline, limit)) for _ in range(BURST)]
    return sum(t.result() is not None for t in tasks)


async def run(cap):
    seller = LimitedSeller("seller-c", 150, 1229, workers=WORKERS)
    with seller.running() as port:
        limit = asyncio.Semaphore(cap) if cap else None
        start = time.monotonic()
        first = asyncio.create_task(burst(port, limit))
        await asyncio.sleep(0.4)  # the second burst arrives 400 ms after the first
        second = await burst(port, limit)
        useful = await first + second
        print(f"burst 1 answered {first.result()} of {BURST}; burst 2 answered {second} of {BURST}")
        await asyncio.sleep(1.3)  # let the seller finish whatever is still queued
        busy_ms = round((seller.last_done - start) * 10) * 100
        print(
            f"seller jobs done: {seller.jobs_done}; useful: {useful}; seller busy until about {busy_ms:,} ms"
        )


async def main():
    print(f"-- no cap: two bursts of {BURST} calls, seller with {WORKERS} workers --")
    await run(cap=0)
    print(f"-- Semaphore({WORKERS}), deadline around the wait --")
    await run(cap=WORKERS)


if __name__ == "__main__":
    asyncio.run(main())

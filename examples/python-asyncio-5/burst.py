"""500 calls to seller-a at once, in a process allowed 256 open files: no cap vs a cap of 50.

The calls run in a child process whose open-file limit is lowered, so the seller servers
(which run in this process) are not affected by the limit.
"""

import asyncio
import errno
import resource
import subprocess
import sys

from sellers_net import running_sellers

CALLS, FILE_LIMIT = 500, 256


async def call(port, stats):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)  # one more file descriptor
    stats["open"] += 1
    stats["peak"] = max(stats["peak"], stats["open"])
    try:
        writer.write(b"kettle-1l\n")
        await writer.drain()
        return await reader.readline()
    finally:
        stats["open"] -= 1
        writer.close()
        await writer.wait_closed()


async def capped(limit, port, stats):
    async with limit:
        return await call(port, stats)


async def burst(port, cap):
    stats = {"open": 0, "peak": 0}
    limit = asyncio.Semaphore(cap) if cap else None
    start = asyncio.get_running_loop().time()
    tasks = []
    try:
        async with asyncio.TaskGroup() as tg:
            for _ in range(CALLS):
                coro = capped(limit, port, stats) if limit else call(port, stats)
                tasks.append(tg.create_task(coro))
    except* OSError as group:
        codes = {errno.errorcode.get(e.errno, str(e.errno)) for e in group.exceptions}
        answered = sum(1 for t in tasks if t.done() and not t.cancelled() and not t.exception())
        print(f"answered {answered} of {CALLS}; TaskGroup failed, error codes: {sorted(codes)}")
    else:
        ms = round((asyncio.get_running_loop().time() - start) * 10) * 100
        print(f"answered {len(tasks)} of {CALLS} in about {ms:,} ms; most open at once: {stats['peak']}")


def client(port, cap):
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (FILE_LIMIT, hard))  # lowering is always allowed
    asyncio.run(burst(port, cap))


def main():
    with running_sellers() as ports:
        for cap in (0, 50):
            label = "no cap" if cap == 0 else f"Semaphore({cap})"
            print(f"-- {CALLS} calls to seller-a at once, {label}, open-file limit {FILE_LIMIT} --")
            args = [sys.executable, __file__, "--client", str(ports["seller-a"]), str(cap)]
            print(subprocess.run(args, capture_output=True, text=True, check=True).stdout, end="")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--client"]:
        client(int(sys.argv[2]), int(sys.argv[3]))
    else:
        main()

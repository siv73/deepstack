"""Two locks taken in opposite orders, with an await between them: both Tasks wait forever."""

import asyncio
import re

cache_lock = asyncio.Lock()  # protects the price cache
quota_lock = asyncio.Lock()  # protects seller-d's call counter


def state(lock):
    return re.sub(r"<asyncio.locks.Lock object at 0x[0-9a-f]+ (.*)>", r"\1", repr(lock))


async def refill(first, second, log):  # takes `first`, does some work, then needs `second`
    async with first:
        await asyncio.sleep(0.01)  # e.g. ask seller-d
        async with second:
            log.append("refill done")


async def report(first, second, log):
    async with first:
        await asyncio.sleep(0.01)  # e.g. read the counter from the metrics store
        async with second:
            log.append("report done")


async def run(order_of_report):
    log = []
    tasks = [
        asyncio.create_task(refill(cache_lock, quota_lock, log), name="refill"),
        asyncio.create_task(report(*order_of_report, log), name="report"),
    ]
    done, pending = await asyncio.wait(tasks, timeout=1.0)  # wait() cancels nothing (Part 3)
    print(f"  after 1 s: finished {sorted(t.get_name() for t in done) or 'none'}; log {log}")
    if pending:
        print(f"  still waiting: {sorted(t.get_name() for t in pending)}")
        print(f"  cache_lock {state(cache_lock)}; quota_lock {state(quota_lock)}")
        for task in pending:
            task.cancel()
        await asyncio.wait(pending)


async def main():
    print("-- refill takes cache then quota; report takes quota then cache --")
    await run((quota_lock, cache_lock))
    print("-- both take cache, then quota --")
    await run((cache_lock, quota_lock))


if __name__ == "__main__":
    asyncio.run(main())

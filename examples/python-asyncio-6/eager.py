"""Eager tasks (3.12+): the coroutine starts inside create_task() and may finish there."""

import asyncio

CACHE = {"kettle-1l": 1199}  # a cached price: answering it needs no network wait


async def cached_price(log, item):
    log.append("lookup started")
    if item in CACHE:
        return CACHE[item]  # returns without ever awaiting
    await asyncio.sleep(0.12)  # a cache miss would ask seller-b
    return 1199


async def run(eager):
    log = []
    task = asyncio.create_task(cached_price(log, "kettle-1l"), eager_start=eager)
    log.append(f"after create_task, done={task.done()}")
    await task
    log.append(f"result {task.result():,}")
    return log


async def main():
    for eager in (False, True):
        print(f"eager_start={eager}:", " | ".join(await run(eager)))
    asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
    log = []
    miss = asyncio.create_task(cached_price(log, "toaster-2s"))  # a miss: it blocks, so it is scheduled
    print(f"eager factory, cache miss: done={miss.done()} after create_task; log={log}")
    print(f"result {await miss:,}")


if __name__ == "__main__":
    asyncio.run(main())

"""Bounded producer/worker pipeline: memory stays flat, workers stop cleanly (3.13+)."""

import asyncio


async def run_pipeline(items, handle, *, workers: int = 4, maxsize: int = 100) -> None:
    queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)

    async def worker() -> None:
        while True:
            try:
                item = await queue.get()
            except asyncio.QueueShutDown:  # shut down and empty: exit
                return
            try:
                await handle(item)
            finally:
                queue.task_done()  # always, even if handle() raised

    async with asyncio.TaskGroup() as tg:  # a failing worker stops the whole pipeline
        for _ in range(workers):
            tg.create_task(worker())
        for item in items:
            await queue.put(item)  # waits while the queue is full: backpressure
        queue.shutdown()  # no more items; workers finish what is queued, then exit

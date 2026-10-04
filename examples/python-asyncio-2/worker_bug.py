"""The classic worker loop that hangs join() forever after one bad item."""

import asyncio


async def worker(queue: asyncio.Queue, handle) -> None:
    while True:
        item = await queue.get()
        await handle(item)  # raises -> task_done() below never runs, worker dies
        queue.task_done()


async def process_all(items, handle, workers: int = 2) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    for item in items:
        queue.put_nowait(item)
    tasks = [asyncio.create_task(worker(queue, handle)) for _ in range(workers)]
    await queue.join()  # waits for a task_done() that will never come
    for t in tasks:
        t.cancel()

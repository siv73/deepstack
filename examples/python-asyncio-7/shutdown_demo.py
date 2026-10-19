"""Queue.shutdown() (Python 3.13+): ending a worker pool without cancelling the workers."""

import asyncio


async def run(immediate):
    queue = asyncio.Queue()
    for n in range(5):
        queue.put_nowait(f"row-{n}")
    written = []

    async def writer():
        while True:
            try:
                row = await queue.get()
            except asyncio.QueueShutDown:  # shut down, and nothing left for this writer
                return
            try:
                await asyncio.sleep(0.010)
                written.append(row)
            finally:
                queue.task_done()

    pool = [asyncio.create_task(writer()) for _ in range(2)]
    await asyncio.sleep(0.015)  # row-0 and row-1 are written; row-2 and row-3 are being written
    queue.shutdown(immediate=immediate)
    try:
        queue.put_nowait("row-5")
    except asyncio.QueueShutDown:
        print(f"immediate={immediate}: put after shutdown raises QueueShutDown;", end=" ")
    await queue.join()
    await asyncio.wait(pool)
    print(
        f"written {written}; writers ended by themselves: {all(t.done() and not t.cancelled() for t in pool)}"
    )


async def main():
    await run(immediate=False)
    await run(immediate=True)


asyncio.run(main())

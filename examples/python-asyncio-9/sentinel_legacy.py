"""Before Queue.shutdown() (Python 3.11 and 3.12): one 'stop' marker per worker ends the pool."""

import asyncio

STOP = object()  # a marker no real row can equal


async def main():
    queue = asyncio.Queue()
    written = []

    async def writer():
        while True:
            row = await queue.get()
            try:
                if row is STOP:
                    return
                await asyncio.sleep(0.010)
                written.append(row)
            finally:
                queue.task_done()

    pool = [asyncio.create_task(writer()) for _ in range(2)]
    for n in range(5):
        await queue.put(f"row-{n}")
    for _ in pool:  # one marker per writer, behind every real row
        await queue.put(STOP)
    await queue.join()
    await asyncio.wait(pool)
    print(
        f"written {written}; writers ended by themselves: {all(t.done() and not t.cancelled() for t in pool)}"
    )


asyncio.run(main())

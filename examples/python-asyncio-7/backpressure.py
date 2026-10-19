"""Backpressure: a bounded queue makes a fast producer run at the speed of a slow consumer.

The producer makes an audit row every 10 ms, at 5, 15, 25 ... ms. The one writer needs 30 ms per row.
"""

import asyncio


async def run(maxsize):
    loop = asyncio.get_running_loop()
    start = loop.time()
    rows = asyncio.Queue(maxsize)
    made = written = 0
    longest_put = 0.0

    async def producer():
        nonlocal made, longest_put
        while True:
            await asyncio.sleep(max(0.0, start + 0.005 + made * 0.010 - loop.time()))  # the next row is due
            asked = loop.time()
            await rows.put(f"row-{made}")  # waits while the queue is full
            longest_put = max(longest_put, loop.time() - asked)
            made += 1

    async def writer():
        nonlocal written
        while True:
            await rows.get()
            await asyncio.sleep(0.030)  # the audit store's write
            written += 1
            rows.task_done()

    tasks = [asyncio.create_task(producer()), asyncio.create_task(writer())]
    await asyncio.sleep(0.300 - (loop.time() - start))
    for t in tasks:
        t.cancel()
    await asyncio.wait(tasks)
    limit = "no limit" if maxsize <= 0 else f"maxsize={maxsize}"
    print(
        f"{limit:>10}: in 300 ms made {made}, written {written}, waiting in the queue {rows.qsize()}, "
        f"longest put() {round(longest_put * 100) * 10} ms"
    )


async def main():
    await run(0)
    await run(3)


asyncio.run(main())

"""A worker pool: a fixed number of Tasks take rows from one queue; join() waits for every row."""

import asyncio
from collections import Counter


async def write_all(rows, writers):
    loop = asyncio.get_running_loop()
    start = loop.time()
    queue = asyncio.Queue()
    for row in rows:
        queue.put_nowait(row)
    done_by = Counter()

    async def writer(name):
        while True:
            await queue.get()  # the row itself does not matter here
            try:
                await asyncio.sleep(0.020)  # one audit write
                done_by[name] += 1
            finally:
                queue.task_done()  # this row is finished, whatever happened

    pool = [asyncio.create_task(writer(f"writer-{n}")) for n in range(1, writers + 1)]
    await queue.join()  # returns when task_done() has been called once per row
    ms = round((loop.time() - start) * 100) * 10
    for task in pool:  # the writers wait in get() forever; stop them
        task.cancel()
    await asyncio.wait(pool)
    print(f"{writers} writer(s): {len(rows)} rows in {ms} ms, rows per writer {sorted(done_by.values())}")


async def main():
    rows = [f"row-{n}" for n in range(9)]
    await write_all(rows, writers=1)
    await write_all(rows, writers=3)


asyncio.run(main())

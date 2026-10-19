"""The worker loop that hangs forever: task_done() after the work, not in finally.

Two audit writers, six rows. The store rejects row-2. Then shutdown waits for join().
"""

import asyncio


class BadRow(Exception):
    pass


async def store_write(row):
    await asyncio.sleep(0.010)
    if row == "row-2":
        raise BadRow(f"store rejected {row}")


async def main(task_done_in_finally):
    queue = asyncio.Queue()
    written = []

    async def writer():
        while True:
            row = await queue.get()
            if task_done_in_finally:
                try:
                    await store_write(row)
                    written.append(row)
                except BadRow:
                    pass  # a real writer would log it and count it
                finally:
                    queue.task_done()
            else:
                await store_write(row)  # raises for row-2: the line below never runs
                written.append(row)
                queue.task_done()

    pool = [asyncio.create_task(writer()) for _ in range(2)]
    for n in range(6):
        queue.put_nowait(f"row-{n}")
    try:
        async with asyncio.timeout(1):
            await queue.join()
        outcome = "join() returned"
    except TimeoutError:
        outcome = "join() still waiting after 1 s"
    alive = sum(not t.done() for t in pool)
    dead = [repr(t.exception()) for t in pool if t.done()]
    print(f"task_done in finally={task_done_in_finally}: {outcome}; written {written};")
    print(
        f"  writers alive {alive} of 2; died with {dead or 'nothing'}; rows left in the queue {queue.qsize()}"
    )
    for t in pool:
        t.cancel()
    await asyncio.gather(*pool, return_exceptions=True)


asyncio.run(main(task_done_in_finally=False))
asyncio.run(main(task_done_in_finally=True))

"""What shield() does not protect: the Task's own group, the caller's wait, and its later failure.

Whether asyncio also logs that later failure depends on the Python version, so this program
silences asyncio's report and prints only what the owner counted.
"""

import asyncio
import logging

from audit import AuditStore
from spawn import failures, spawn

logging.getLogger("gateway.background").addHandler(logging.NullHandler())  # counted, not printed here
logging.getLogger("gateway.background").propagate = False


class DownStore(AuditStore):
    async def write(self, row):
        await asyncio.sleep(0.03)
        raise ConnectionError("audit store refused the connection")


async def owned_by_the_group(store):
    async with asyncio.TaskGroup() as tg:
        task = tg.create_task(store.write("row"))  # the request's own group owns the write
        await asyncio.shield(task)


async def run_and_hang_up(handler, store):
    task = asyncio.create_task(handler(store))
    await asyncio.sleep(0.01)
    task.cancel()  # the shopper hangs up
    await asyncio.wait([task])
    await asyncio.sleep(0.06)


async def main():
    print("-- 1. shield() around a Task that the request's TaskGroup owns --")
    store = AuditStore(ms=40)
    await run_and_hang_up(owned_by_the_group, store)
    print(f"  rows={len(store.rows)}, lost={len(store.lost)}: the group cancelled its own Task")

    print("-- 2. a deadline around shield(): the caller stops waiting, the write goes on --")
    store = AuditStore(ms=40)
    task = spawn(store.write("row"), name="audit")
    try:
        async with asyncio.timeout(0.01):
            await asyncio.shield(task)
    except TimeoutError:
        print(f"  TimeoutError at 10 ms; write done={task.done()}")
    await task
    print(f"  at 40 ms: rows={len(store.rows)}")

    print("-- 3. the shielded write fails after the caller has gone --")

    async def handler(store):
        await asyncio.shield(spawn(store.write("row"), name="audit"))

    asyncio.get_running_loop().set_exception_handler(lambda _loop, _context: None)
    await run_and_hang_up(handler, DownStore())
    print(f"  spawn() counted: {dict(failures)}")


asyncio.run(main())

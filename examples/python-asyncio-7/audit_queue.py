"""Audit rows through a bounded queue to a fixed pool of writers: the same write() as AuditStore.

When the store slows down, the queue fills and write() waits in put(): backpressure that
reaches every request waiting for its row, instead of an ever-growing pile of write Tasks.
"""

import asyncio

from spawn import spawn


class AuditQueue:
    def __init__(self, store, writers=4, maxsize=8):
        self.store, self.writers = store, writers
        self.queue = asyncio.Queue(maxsize)
        self.pool = []

    def start(self):
        self.pool = [spawn(self._writer(), name="audit-writer") for _ in range(self.writers)]

    async def write(self, row):
        committed = asyncio.get_running_loop().create_future()
        await self.queue.put((row, committed))  # full: wait here, the producer slows down
        await committed  # the row is in the store

    async def _writer(self):
        while True:
            try:
                row, committed = await self.queue.get()
            except asyncio.QueueShutDown:  # closed and empty: this writer is finished
                return
            try:
                await self.store.write(row)
                if not committed.done():
                    committed.set_result(None)
            except Exception as exc:  # the store failed: the waiting request hears about it
                if not committed.done():
                    committed.set_exception(exc)
            finally:
                self.queue.task_done()  # always, or join() waits forever

    async def close(self):
        self.queue.shutdown()  # no new rows; writers finish the queued ones, then return
        await self.queue.join()
        await asyncio.wait(self.pool)

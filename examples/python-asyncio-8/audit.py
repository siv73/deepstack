"""The audit log: one row for every request the gateway answers or abandons (a local stub).

The store is reached over the network, so a write takes two round trips: insert, then commit.
A write that is cancelled between the two leaves an uncommitted row, which the store throws away.
"""

import asyncio


class AuditStore:
    def __init__(self, ms=20):
        self.ms = ms  # one write: insert and commit, half each
        self.rows = []  # committed rows: the audit trail
        self.lost = []  # rows whose write was cancelled before its commit

    async def write(self, row):
        try:
            await asyncio.sleep(self.ms / 2000)  # INSERT
            await asyncio.sleep(self.ms / 2000)  # COMMIT
        except asyncio.CancelledError:
            self.lost.append(row)  # the store rolls the insert back
            raise
        self.rows.append(row)

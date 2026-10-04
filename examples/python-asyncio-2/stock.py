"""Check-then-act across an await: a race even on one thread."""

import asyncio


class Stock:
    def __init__(self, units: int) -> None:
        self.units = units
        self.lock = asyncio.Lock()

    async def reserve_racy(self) -> bool:
        if self.units > 0:  # check...
            await asyncio.sleep(0.01)  # ...other tasks run here (audit write, API call)...
            self.units -= 1  # ...act on a stale check
            return True
        return False

    async def reserve_safe(self) -> bool:
        async with self.lock:  # check and act as one step
            return await self.reserve_racy()

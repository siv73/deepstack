"""Same three waits, run one by one and then together."""

import asyncio


async def one_by_one(delays: list[float]) -> None:
    for d in delays:
        await asyncio.sleep(d)  # each await finishes before the next starts


async def together(delays: list[float]) -> None:
    async with asyncio.TaskGroup() as tg:  # all start now; the block waits for all
        for d in delays:
            tg.create_task(asyncio.sleep(d))

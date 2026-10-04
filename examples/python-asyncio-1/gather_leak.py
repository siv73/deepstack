"""One call fails. What happens to the other one?"""

import asyncio


async def fails() -> None:
    await asyncio.sleep(0.01)
    raise ValueError("payment API returned 500")


async def slow_write(done: list[str]) -> None:
    await asyncio.sleep(0.1)
    done.append("wrote row")  # still runs after gather() already raised


async def with_gather(done: list[str]) -> None:
    await asyncio.gather(fails(), slow_write(done))


async def with_taskgroup(done: list[str]) -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fails())
        tg.create_task(slow_write(done))  # cancelled when fails() raises

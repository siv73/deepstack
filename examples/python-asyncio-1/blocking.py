"""A heartbeat that should tick every 10 ms, next to a handler that waits 300 ms."""

import asyncio
import time


async def handler_blocking() -> None:
    time.sleep(0.3)  # sync call: the whole loop stops for 300 ms


async def handler_fixed() -> None:
    await asyncio.to_thread(time.sleep, 0.3)  # runs in a worker thread


async def worst_heartbeat_delay(handler) -> float:
    worst = 0.0

    async def heartbeat() -> None:
        nonlocal worst
        for _ in range(40):
            start = time.perf_counter()
            await asyncio.sleep(0.01)
            worst = max(worst, time.perf_counter() - start - 0.01)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(heartbeat())
        tg.create_task(handler())
    return worst

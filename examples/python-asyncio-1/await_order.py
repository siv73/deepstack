"""await on a coroutine vs await on a task: who gets to run first?"""

import asyncio


async def run(wrap_in_task: bool) -> list[str]:
    log: list[str] = []

    async def a() -> None:
        log.append("a")

    async def b() -> None:
        log.append("b")

    task_b = asyncio.create_task(b())  # scheduled, not running yet
    for _ in range(3):
        if wrap_in_task:
            await asyncio.create_task(a())  # a task: hands control to the loop
        else:
            await a()  # a bare coroutine: runs inline, no hand-off
    await task_b
    return log

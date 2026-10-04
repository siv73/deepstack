"""Eager tasks (3.12+) start running inside create_task(): order changes."""

import asyncio


async def cached_lookup(log: list[str]) -> str:
    log.append("lookup ran")  # a cache hit: finishes without awaiting
    return "hit"


async def run(eager: bool) -> list[str]:
    log: list[str] = []
    if eager:
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
    task = asyncio.create_task(cached_lookup(log))
    log.append("after create_task")
    await task
    return log

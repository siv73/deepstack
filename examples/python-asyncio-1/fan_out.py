"""Fetch many URLs at once: capped, under one deadline, failing as a group."""

import asyncio
from collections.abc import Awaitable, Callable

Fetch = Callable[[str], Awaitable[bytes]]


async def fetch_all(urls: list[str], fetch: Fetch, *, limit: int = 20, deadline: float = 10.0) -> list[bytes]:
    sem = asyncio.Semaphore(limit)  # at most `limit` requests in flight

    async def one(url: str) -> bytes:
        async with sem:
            return await fetch(url)

    async with asyncio.timeout(deadline):  # one deadline for the whole batch
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(one(u)) for u in urls]
    return [t.result() for t in tasks]  # same order as urls

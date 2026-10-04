"""Async generator cleanup runs late unless you close the generator yourself."""

import asyncio
import contextlib


async def rows(log: list[str]):
    log.append("cursor opened")
    try:
        for i in range(1_000):
            yield i
    finally:
        await asyncio.sleep(0.01)  # async cleanup: close the server-side cursor
        log.append("cursor closed")


async def first_big_leaky(log: list[str]) -> int:
    async for r in rows(log):
        if r >= 3:
            return r  # generator left suspended; cleanup deferred to GC/shutdown


async def first_big_safe(log: list[str]) -> int:
    async with contextlib.aclosing(rows(log)) as it:
        async for r in it:
            if r >= 3:
                return r  # aclosing() runs the cleanup here, in this task

"""Calling a sync-only SDK from async code without freezing the loop."""

import asyncio
import time


def legacy_sdk_get(key: str) -> str:
    time.sleep(0.2)  # a blocking network call inside a library you can't change
    return f"value:{key}"


async def get_many(keys: list[str]) -> list[str]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(asyncio.to_thread(legacy_sdk_get, k)) for k in keys]
    return [t.result() for t in tasks]

"""Async context managers and AsyncExitStack: whatever was opened is closed, last opened first."""

import asyncio
import contextlib

STARTUP = ["audit writers", "metrics flusher", "seller-e feed", "listener"]  # gateway v9's start order


@contextlib.asynccontextmanager
async def resource(name, fail=False):
    if fail:
        raise OSError(f"{name}: address already in use")
    print(f"  open  {name}")
    try:
        yield name
    finally:
        await asyncio.sleep(0.01)  # closing may wait: an async __aexit__
        print(f"  close {name}")


async def start(fail_at=None):
    async with contextlib.AsyncExitStack() as stack:
        for name in STARTUP:
            await stack.enter_async_context(resource(name, fail=name == fail_at))
        print("  serving")


async def main():
    print("-- normal start and stop --")
    await start()
    print("-- the listener cannot open --")
    try:
        await start(fail_at="listener")
    except OSError as exc:
        print(f"  start failed: {exc}")


asyncio.run(main())

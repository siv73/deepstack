"""The toy loop only understands its own ("sleep", ms) requests, not real waits."""

import asyncio

from toyloop import ToyLoop


async def ask_with_asyncio_sleep():
    await asyncio.sleep(0.08)  # asyncio's sleep expects asyncio's own loop


async def ask_with_bare_yield():
    await asyncio.sleep(0)  # yields a bare None to whoever drives it


for coro_fn in (ask_with_asyncio_sleep, ask_with_bare_yield):
    loop = ToyLoop()
    loop.spawn(coro_fn(), "seller-a")
    try:
        loop.run()
    except (RuntimeError, TypeError) as error:
        print(f"{coro_fn.__name__}: {type(error).__name__}: {error}")

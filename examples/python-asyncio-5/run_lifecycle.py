"""What asyncio.run does after main() returns: three clean-up jobs, then close the loop."""

import asyncio
import time

kept = []  # strong references, so nothing is garbage-collected before shutdown


async def leftover():
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        print("2. leftover task: cancelled")
        raise  # let the cancellation finish the task


async def prices():
    try:
        yield 1199
        yield 1229
    finally:
        print("3. async generator: closed (its finally ran)")


async def main():
    loop = asyncio.get_running_loop()
    kept.append(loop)
    kept.append(asyncio.create_task(leftover()))  # started, never awaited
    gen = prices()
    kept.append(gen)
    print(f"first price: {await anext(gen):,}")  # the generator is left paused
    loop.run_in_executor(None, time.sleep, 0.2)  # a thread in the default executor
    print("1. main() returns")
    return "main's result"


start = time.monotonic()
result = asyncio.run(main())
ms = round((time.monotonic() - start) * 100) * 10
print(f"4. asyncio.run returned {result!r} after {ms} ms; loop closed: {kept[0].is_closed()}")

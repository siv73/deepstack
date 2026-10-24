"""Rung 3: what the virtual clock moves, and what it does not."""

import asyncio
import time

from virtual_clock import VirtualClockLoop


async def main():
    loop = asyncio.get_running_loop()
    real = time.perf_counter()

    def line(what):
        took = round((time.perf_counter() - real) * 1000)
        print(f"{what:<46} loop.time() = {loop.time():.3f} s   real time so far: {took} ms")

    line("start")
    await asyncio.sleep(0.9)
    line("after asyncio.sleep(0.9)")
    try:
        async with asyncio.timeout(0.25):
            await asyncio.Event().wait()
    except TimeoutError:
        line("after asyncio.timeout(0.25) fired")
    first = asyncio.create_task(asyncio.sleep(0.2))
    second = asyncio.create_task(asyncio.sleep(0.1))
    done, _ = await asyncio.wait([first, second], return_when=asyncio.FIRST_COMPLETED)
    line(f"first of two sleeps done: the {'0.1 s' if second in done else '0.2 s'} one")
    await first
    time.sleep(0.05)  # a blocking call: real time passes, the virtual clock does not move
    line("after time.sleep(0.05) on the loop's thread")


asyncio.run(main(), loop_factory=VirtualClockLoop)

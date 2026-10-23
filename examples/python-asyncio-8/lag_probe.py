"""Measure loop lag with public APIs only: how late does a 100 ms timer fire?"""

import asyncio
import time


async def lag_probe(samples, every=0.1):
    loop = asyncio.get_running_loop()
    for _ in range(samples):
        expected = loop.time() + every
        await asyncio.sleep(every)
        lag_ms = (loop.time() - expected) * 1000
        print(f"loop lag: {round(lag_ms / 10) * 10} ms")


async def blocking_handler():
    await asyncio.sleep(0.15)
    time.sleep(0.3)  # a blocking call on the loop's thread (Part 1's bug)


async def main():
    probe = asyncio.create_task(lag_probe(samples=4))
    await blocking_handler()
    await probe


asyncio.run(main())

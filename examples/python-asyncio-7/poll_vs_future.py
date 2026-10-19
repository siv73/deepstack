"""Busy waiting inside asyncio: polling a flag with sleep(0) vs awaiting a Future."""

import asyncio
import time

box = {}


async def seller_b(fut):
    await asyncio.sleep(0.12)
    box["price"] = 1199
    fut.set_result(1199)


async def poll_flag():
    while "price" not in box:  # wakes up on every loop iteration to check
        await asyncio.sleep(0)
    return box["price"]


async def run(label, waiter):
    box.clear()
    fut = asyncio.get_running_loop().create_future()
    seller = asyncio.create_task(seller_b(fut))
    start, cpu_start = time.monotonic(), time.process_time()
    price = await (poll_flag() if waiter == "poll" else fut)
    wall, cpu = time.monotonic() - start, time.process_time() - cpu_start
    await seller
    share = "over 50%" if cpu / wall > 0.5 else "under 5%" if cpu / wall < 0.05 else f"{cpu / wall:.0%}"
    print(f"{label}: got {price:,} after about {round(wall * 100) * 10} ms; CPU busy {share}")


async def main():
    await run("polling with sleep(0)", "poll")
    await run("awaiting a Future   ", "future")


asyncio.run(main())

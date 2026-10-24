"""Rung 2: loop lag as a metric, in four situations. Which ones does it see?"""

import asyncio
import time

from observe import LagMonitor


def spin(ms):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:  # CPU work that never awaits
        pass


async def busy_request():
    spin(10)  # 10 ms of parsing and ranking on the loop's thread
    await asyncio.sleep(0)


async def phase(lag, name, work):
    lag.take_worst()
    count_before = lag.histogram.count
    await work()
    await asyncio.sleep(0.12)  # let the monitor take a sample after the work
    print(
        f"{name:<44} worst lag {round(lag.take_worst() / 10) * 10:4} ms  "
        f"({lag.histogram.count - count_before} samples)"
    )


async def main():
    lag = LagMonitor(every=0.05)
    lag.start()

    async def idle():
        await asyncio.sleep(0.5)

    async def blocked():
        await asyncio.sleep(0.05)
        time.sleep(0.3)  # one blocking call on the loop's thread (Part 4's trap 2)

    async def overloaded():
        await asyncio.gather(*(busy_request() for _ in range(30)))  # 30 x 10 ms queued at once

    async def stuck():
        never = asyncio.Event()
        waiters = [asyncio.create_task(never.wait()) for _ in range(5)]  # 5 requests waiting forever
        await asyncio.sleep(0.5)
        for task in waiters:
            task.cancel()

    await phase(lag, "idle, 500 ms", idle)
    await phase(lag, "one 300 ms blocking call", blocked)
    await phase(lag, "30 requests x 10 ms of CPU, all at once", overloaded)
    await phase(lag, "5 requests stuck on an await, 500 ms", stuck)
    await lag.stop()
    h = lag.histogram
    print(
        f"all samples: {h.count}; at or under 50 ms: {h.at_or_under(50)}; "
        f"over 250 ms: {h.count - h.at_or_under(250)}"
    )


asyncio.run(main())

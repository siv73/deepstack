"""A Semaphore caps how many seller calls are in flight; the rest wait for a free slot."""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers


async def capped_call(limit, stats, start, name, port):
    async with limit:  # take a slot, or wait in line until one is released
        stats["now"] += 1
        stats["peak"] = max(stats["peak"], stats["now"])
        print(f"{ms_since(start):5} ms  {name} starts ({stats['now']} in flight)")
        try:
            return await ask_seller(start, name, port, "kettle-1l")
        finally:
            stats["now"] -= 1  # the slot is released when the async with block ends


async def main():
    limit = asyncio.Semaphore(3)  # at most 3 seller calls at once
    stats = {"now": 0, "peak": 0}
    with running_sellers() as ports:
        start = asyncio.get_running_loop().time()
        async with asyncio.TaskGroup() as tg:
            for name, port in ports.items():
                tg.create_task(capped_call(limit, stats, start, name, port))
        print(f"all done after {ms_since(start):,} ms; most in flight at once: {stats['peak']}")


if __name__ == "__main__":
    asyncio.run(main())

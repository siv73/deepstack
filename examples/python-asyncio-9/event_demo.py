"""asyncio.Event: many Tasks wait for one thing to happen, and are all woken together."""

import asyncio

start = 0.0


def ms():
    return round((asyncio.get_running_loop().time() - start) * 100) * 10


async def shopper(name, arrives_ms, warm):
    await asyncio.sleep(arrives_ms / 1000)
    waited_from = ms()
    await warm.wait()  # parked on a Future until set(); returns at once if already set
    print(f"{ms():4} ms  {name} served (arrived {waited_from} ms)")


async def warm_up(warm):
    await asyncio.sleep(0.1)  # load seller-e's prices into the cache: 100 ms
    print(f"{ms():4} ms  cache warm: set()")
    warm.set()
    await asyncio.sleep(0.1)
    print(f"{ms():4} ms  cache cleared for a reload: clear()")
    warm.clear()
    await asyncio.sleep(0.1)
    print(f"{ms():4} ms  cache warm again: set()")
    warm.set()


async def main():
    global start
    start = asyncio.get_running_loop().time()
    warm = asyncio.Event()  # starts unset
    async with asyncio.TaskGroup() as tg:
        tg.create_task(warm_up(warm))
        for n, arrives in enumerate([0, 20, 40, 150, 250], start=1):
            tg.create_task(shopper(f"shopper-{n}", arrives, warm))


if __name__ == "__main__":
    asyncio.run(main())

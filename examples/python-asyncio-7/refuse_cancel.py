"""Three ways to give a slow price cache 20 ms. Two refuse a cancel; only one keeps the books."""

import asyncio


class SlowCache:
    async def get(self, item):
        await asyncio.sleep(0.05)  # the cache is slow today: 50 ms
        return None


async def handmade(cache, item):
    me = asyncio.current_task()
    timer = asyncio.get_running_loop().call_later(0.02, me.cancel)
    try:
        return await cache.get(item)
    except asyncio.CancelledError:
        return None  # BUG: refuses every cancel, and leaves the count at 1
    finally:
        timer.cancel()


async def handmade_uncancel(cache, item):
    me = asyncio.current_task()
    timer = asyncio.get_running_loop().call_later(0.02, me.cancel)
    try:
        return await cache.get(item)
    except asyncio.CancelledError:
        me.uncancel()  # keeps the count right, but still refuses every cancel
        return None
    finally:
        timer.cancel()


async def with_timeout(cache, item):
    try:
        async with asyncio.timeout(0.02):
            return await cache.get(item)
    except TimeoutError:
        return None


LOOKUPS = {
    "hand-made limit, no uncancel()": handmade,
    "hand-made limit with uncancel()": handmade_uncancel,
    "asyncio.timeout(0.02)": with_timeout,
}


async def handler(lookup, log):
    await lookup(SlowCache(), "kettle-1l")
    log.append(f"skipped the cache; cancelling()={asyncio.current_task().cancelling()}")
    await asyncio.sleep(0.03)  # goes on to ask the sellers
    log.append("asked the sellers")


async def main():
    print("-- the cache is slow; nobody else cancels --")
    for name, lookup in LOOKUPS.items():
        log = []
        await asyncio.create_task(handler(lookup, log))
        print(f"  {name:<32} {'; '.join(log)}")
    print("-- the shopper hangs up 10 ms into the lookup --")
    for name, lookup in LOOKUPS.items():
        log = []
        task = asyncio.create_task(handler(lookup, log))
        asyncio.get_running_loop().call_later(0.01, task.cancel)
        await asyncio.wait([task])
        print(f"  {name:<32} {'; '.join(log) or 'stopped'}; cancelled={task.cancelled()}")


if __name__ == "__main__":
    asyncio.run(main())

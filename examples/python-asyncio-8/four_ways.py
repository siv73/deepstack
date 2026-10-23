"""One shared price map, four ways to keep it safe: a lock, single-flight, an owner Task, a snapshot."""

import asyncio
import types
from collections import Counter

from single_flight import SingleFlight

ITEMS = ("kettle-1l", "toaster-2s", "iron-x1")
calls = Counter()


async def ask_seller_c(item):  # 150 ms, as seller-c
    calls[item] += 1
    await asyncio.sleep(0.15)
    return 1229


class OneLock:
    def __init__(self):
        self.prices, self.lock = {}, asyncio.Lock()

    async def price(self, item):
        async with self.lock:  # every item behind one lock, held across the seller call
            if item not in self.prices:
                self.prices[item] = await ask_seller_c(item)
            return self.prices[item]


class PerKeyFlight:
    def __init__(self):
        self.prices, self.flights = {}, SingleFlight()

    async def fill(self, item):
        self.prices[item] = await ask_seller_c(item)
        return self.prices[item]

    async def price(self, item):
        if item in self.prices:
            return self.prices[item]
        return await asyncio.shield(self.flights.start(item, lambda: self.fill(item), name=item))


class OwnerTask:
    """Only the owner Task touches the map; everyone else sends it a message and waits for the reply."""

    def __init__(self):
        self.prices, self.inbox, self.task = {}, asyncio.Queue(), None

    async def run(self):
        while True:
            item, reply = await self.inbox.get()
            if item not in self.prices:
                self.prices[item] = await ask_seller_c(item)  # one message at a time
            reply.set_result(self.prices[item])

    async def price(self, item):
        if self.task is None:
            self.task = asyncio.create_task(self.run())
        reply = asyncio.get_running_loop().create_future()
        await self.inbox.put((item, reply))
        return await reply


class Snapshot:
    """A refresher Task builds a new map and swaps it in whole; readers never wait and never lock."""

    def __init__(self):
        self.prices = types.MappingProxyType({})  # read-only view: nobody changes it in place

    async def refresh(self):
        fresh = {}
        for item in ITEMS:
            fresh[item] = await ask_seller_c(item)
        self.prices = types.MappingProxyType(fresh)  # one assignment: readers see old or new, never half

    async def price(self, item):
        return self.prices[item]


async def compare(cache):
    loop = asyncio.get_running_loop()
    calls.clear()
    if isinstance(cache, Snapshot):
        await cache.refresh()  # done before requests arrive, then again on a timer
        calls.clear()
    slowest = 0.0

    async def request(item):
        nonlocal slowest
        start = loop.time()
        await cache.price(item)
        slowest = max(slowest, loop.time() - start)

    async with asyncio.TaskGroup() as tg:
        for _ in range(30):
            for item in ITEMS:
                tg.create_task(request(item))
    if isinstance(cache, OwnerTask):
        cache.task.cancel()
        await asyncio.wait([cache.task])
    name = type(cache).__name__
    wait_ms = round(slowest * 100) * 10
    print(f"  {name:13} seller calls during the burst: {sum(calls.values())}; slowest wait {wait_ms:3} ms")


async def main():
    print(f"-- 90 requests at once: 30 each for {', '.join(ITEMS)}; seller-c takes 150 ms --")
    for cache in (OneLock(), PerKeyFlight(), OwnerTask(), Snapshot()):
        await compare(cache)


if __name__ == "__main__":
    asyncio.run(main())

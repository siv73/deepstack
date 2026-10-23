"""One cache lock held across a slow seller call: a cached item waits for someone else's miss."""

import asyncio

from price_cache import PriceCache
from sellers import Offer
from single_flight import SingleFlight

start = 0.0


def ms():
    return round((asyncio.get_running_loop().time() - start) * 100) * 10


async def ask_seller_e(item):
    await asyncio.sleep(0.9)  # seller-e's 900 ms
    return Offer("seller-e", 1149)


class OneLock:
    """Protects the whole cache with one Lock, held while the seller is asked."""

    def __init__(self):
        self.cache, self.lock = PriceCache(ttl=30), asyncio.Lock()

    async def price(self, item):
        async with self.lock:  # check, ask and store as one step: no duplicate calls
            offer = self.cache.get("seller-e", item)
            if offer is None:
                offer = await ask_seller_e(item)  # 900 ms with the lock held
                self.cache.put("seller-e", item, offer)
            return offer


class PerKey:
    """Single-flight per item: only callers of the same item wait for the same call."""

    def __init__(self):
        self.cache, self.flights = PriceCache(ttl=30), SingleFlight()

    async def fill(self, item):
        offer = await ask_seller_e(item)
        self.cache.put("seller-e", item, offer)
        return offer

    async def price(self, item):
        offer = self.cache.get("seller-e", item)
        if offer is None:
            task = self.flights.start(item, lambda: self.fill(item), name=f"fill {item}")
            offer = await asyncio.shield(task)
        return offer


async def shopper(cache, name, item, arrives_ms):
    await asyncio.sleep(arrives_ms / 1000)
    asked = ms()
    await cache.price(item)
    print(f"  {name} asks for {item:10} at {asked:3} ms, answered at {ms():4} ms")


async def main():
    global start
    for cache in (OneLock(), PerKey()):
        print(f"-- {type(cache).__name__}: kettle-1l is already cached, toaster-2s is not --")
        start = asyncio.get_running_loop().time()
        cache.cache.put("seller-e", "kettle-1l", Offer("seller-e", 1149))
        async with asyncio.TaskGroup() as tg:
            tg.create_task(shopper(cache, "shopper-1", "toaster-2s", 0))
            tg.create_task(shopper(cache, "shopper-2", "kettle-1l", 10))


if __name__ == "__main__":
    asyncio.run(main())

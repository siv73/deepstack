"""Check-then-act across an await: a price cache that every request fills for itself."""

import asyncio
from collections import Counter

from sellers import Offer

calls = Counter()  # seller calls actually made, by seller


async def ask_seller_c(sku):
    calls["seller-c"] += 1
    await asyncio.sleep(0.15)  # seller-c's 150 ms
    return Offer("seller-c", 1229)


class NaiveCache:
    def __init__(self):
        self.prices = {}

    async def price(self, sku):
        if sku not in self.prices:  # check ...
            self.prices[sku] = await ask_seller_c(sku)  # ... act, 150 ms and one await later
        return self.prices[sku]


async def main():
    loop = asyncio.get_running_loop()
    cache = NaiveCache()
    start = loop.time()
    async with asyncio.TaskGroup() as tg:
        for _ in range(100):
            tg.create_task(cache.price("kettle-1l"))
    took = round((loop.time() - start) * 100) * 10
    print(f"100 requests at once: seller-c asked {calls['seller-c']} times; all answered after {took} ms")
    calls.clear()
    async with asyncio.TaskGroup() as tg:
        for _ in range(100):
            tg.create_task(cache.price("kettle-1l"))
    print(f"100 more requests, after the cache is filled: seller-c asked {calls['seller-c']} times")


if __name__ == "__main__":
    asyncio.run(main())

"""100 requests for one item at once: a naive cache asks every seller 100 times, single-flight once."""

import asyncio
from collections import Counter

from price_cache import PriceCache
from sellers import BUDGET_MS, SELLERS, Offer
from single_flight import SingleFlight

calls = Counter()  # seller calls actually made


async def ask(s, item):  # a stand-in seller: waits its latency, answers its price
    calls[s.name] += 1
    await asyncio.sleep(s.latency_ms / 1000)
    return Offer(s.name, s.price)


class Naive:
    def __init__(self):
        self.cache = PriceCache(ttl=30)

    async def price(self, s, item):
        offer = self.cache.get(s.name, item)
        if offer is None:  # check, then await the seller, then store: every request does all three
            offer = await ask(s, item)
            self.cache.put(s.name, item, offer)
        return offer


class SingleFlightCache:
    def __init__(self):
        self.cache, self.flights = PriceCache(ttl=30), SingleFlight()

    async def fill(self, s, item):
        offer = await ask(s, item)
        self.cache.put(s.name, item, offer)
        return offer

    async def price(self, s, item):
        offer = self.cache.get(s.name, item)
        if offer is None:
            fill = self.flights.start((s.name, item), lambda: self.fill(s, item), name=f"fill {s.name}")
            offer = await asyncio.shield(fill)  # our deadline may cut our wait, never the fill
        return offer


async def request(cache, item, deadline):
    async def one(s):
        try:
            async with asyncio.timeout_at(deadline):
                return await cache.price(s, item)
        except TimeoutError:
            return None

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(one(s)) for s in SELLERS]
    offers = [t.result() for t in tasks if t.result() is not None]
    return min(offers, key=lambda o: o.price)


async def wave(cache, label):
    loop = asyncio.get_running_loop()
    calls.clear()
    deadline = loop.time() + BUDGET_MS / 1000
    async with asyncio.TaskGroup() as tg:
        answers = [tg.create_task(request(cache, "kettle-1l", deadline)) for _ in range(100)]
    best = Counter(f"{a.result().seller} {a.result().price:,}" for a in answers)
    print(f"  {label}: answers {dict(best)}; seller calls {dict(sorted(calls.items())) or 'none'}")


async def main():
    for label, cache in (("naive cache", Naive()), ("single-flight cache", SingleFlightCache())):
        print(f"-- {label}: 100 requests at once, then 100 more 1 s later --")
        await wave(cache, "first 100")
        await asyncio.sleep(1)  # seller-e's 900 ms answer arrives in the meantime
        await wave(cache, "next 100 ")


if __name__ == "__main__":
    asyncio.run(main())

"""asyncio.Condition: wait, under a lock, until shared state reaches the state you need."""

import asyncio

from sellers import SELLERS, Offer

start = 0.0


def ms():
    return round((asyncio.get_running_loop().time() - start) * 100) * 10


async def seller(s, offers, cond):
    await asyncio.sleep(s.latency_ms / 1000)
    async with cond:  # change the shared list only while holding the condition's lock
        offers.append(Offer(s.name, s.price))
        print(f"{ms():4} ms  {s.name} added; offers so far: {len(offers)}")
        cond.notify_all()  # wake every waiter so each re-checks its own predicate


async def quorum(offers, cond, needed):
    async with cond:
        await cond.wait_for(lambda: len(offers) >= needed)  # releases the lock while it waits
        best = min(offers, key=lambda o: o.price)
        print(f"{ms():4} ms  quorum of {needed}: best so far {best.seller} at {best.price:,}")


async def main():
    global start
    start = asyncio.get_running_loop().time()
    offers, cond = [], asyncio.Condition()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(quorum(offers, cond, 3))
        for s in SELLERS[:4]:
            tg.create_task(seller(s, offers, cond))
    try:
        cond.notify()  # without holding the lock
    except RuntimeError as e:
        print(f"notify() without the lock: RuntimeError: {e}")


if __name__ == "__main__":
    asyncio.run(main())

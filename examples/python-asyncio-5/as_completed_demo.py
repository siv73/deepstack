"""as_completed(): handle each seller's answer the moment it arrives, in finishing order."""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers

GOOD_ENOUGH = 1200  # stop at the first offer at or below this price


async def main():
    with running_sellers() as ports:
        start = asyncio.get_running_loop().time()
        names = ["seller-e", "seller-d", "seller-c", "seller-b", "seller-a"]  # slowest first
        tasks = [asyncio.create_task(ask_seller(start, n, ports[n], "kettle-1l"), name=n) for n in names]
        async for done in asyncio.as_completed(tasks):  # yields the original Tasks, as they finish
            offer = done.result()
            print(f"{ms_since(start):5} ms  handled {done.get_name()}")
            if offer.price <= GOOD_ENOUGH:
                print(f"good enough: {offer.seller} at {offer.price:,}")
                break
        still_running = [t.get_name() for t in tasks if not t.done()]
        print("still running after the loop:", still_running)
        for t in tasks:
            t.cancel()  # as_completed does not cancel them for us
        await asyncio.gather(*tasks, return_exceptions=True)
        print("cancelled:", [t.get_name() for t in tasks if t.cancelled()])


if __name__ == "__main__":
    asyncio.run(main())

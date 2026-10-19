"""seller-c's limits: a cap of 3 calls in flight, a line of 2. Ten requests ask at once, 250 ms each."""

import asyncio
from collections import Counter

from limits import SellerLimits, Skipped


async def main():
    loop = asyncio.get_running_loop()
    start = loop.time()
    limits = SellerLimits(caps={"seller-c": 3}, max_waiting={"seller-c": 2}, rates={})
    outcome = Counter()

    async def ask_seller_c():
        await asyncio.sleep(0.150)  # seller-c's 150 ms
        return "seller-c 1229"

    async def request():
        try:
            async with asyncio.timeout_at(start + 0.250):  # the request's deadline covers the line
                await limits.call("seller-c", ask_seller_c)
            outcome[f"answered by {round((loop.time() - start) * 100) * 10} ms"] += 1
        except TimeoutError:
            outcome["cut by the 250 ms deadline"] += 1
        except Skipped:
            outcome["skipped at 0 ms: line full"] += 1

    async with asyncio.TaskGroup() as tg:
        for _ in range(10):
            tg.create_task(request())
        await asyncio.sleep(0)
        cap, line = limits.caps["seller-c"], limits.waiting["seller-c"]
        print(f"at 0 ms: cap locked={cap.locked()}, waiting in line={line}")
    for what, n in sorted(outcome.items()):
        print(f"  {n} {what}")


asyncio.run(main())

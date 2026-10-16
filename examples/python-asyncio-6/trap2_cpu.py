"""Trap 2b: CPU work. On the loop it freezes everything; threads still take turns on one GIL;
a process pool runs it on other cores while the loop stays free.

Each scoring is calibrated to about 100 ms of CPU on whatever machine runs this.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from scoring import rounds_for, score_offers
from sellers import SELLERS, Offer

OFFERS = [Offer(s.name, s.price) for s in SELLERS[:4]]  # what seller-a to seller-d returned
REQUESTS, WORKERS = 6, 2


async def heartbeat(stop, lags):
    """A timer that should fire every 10 ms; records how late each firing was."""
    loop = asyncio.get_running_loop()
    while not stop.is_set():
        due = loop.time() + 0.01
        await asyncio.sleep(0.01)
        lags.append(loop.time() - due)


async def run(label, rounds, pool=None):
    loop = asyncio.get_running_loop()
    stop, lags = asyncio.Event(), []
    beat = asyncio.create_task(heartbeat(stop, lags))
    await asyncio.sleep(0.05)

    async def score():
        if pool is None:
            return score_offers(OFFERS, rounds)  # BUG: CPU work on the loop's thread
        return await loop.run_in_executor(pool, score_offers, OFFERS, rounds)

    start = loop.time()
    async with asyncio.TaskGroup() as tg:
        scored = [tg.create_task(score()) for _ in range(REQUESTS)]
    took = loop.time() - start
    stop.set()
    await beat
    best = scored[0].result()[0]
    print(
        f"{label}: {REQUESTS} scorings in about {round(took * 20) * 50} ms; "
        f"worst timer lag {round(max(lags) * 100) * 10} ms; best {best.seller} at {best.price:,}"
    )


async def main():
    rounds = rounds_for(100)  # about 100 ms of CPU per scoring
    loop = asyncio.get_running_loop()
    await run("on the loop      ", rounds)
    with ThreadPoolExecutor(max_workers=WORKERS) as threads:
        await run("2 threads        ", rounds, threads)
    with ProcessPoolExecutor(max_workers=WORKERS) as processes:
        warm = [loop.run_in_executor(processes, score_offers, OFFERS, 1) for _ in range(WORKERS)]
        await asyncio.gather(*warm)  # start the worker processes before timing
        await run("2 processes      ", rounds, processes)


if __name__ == "__main__":
    asyncio.run(main())

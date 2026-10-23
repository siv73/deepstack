"""Gateway v4: a TaskGroup, one cap shared by every request, and one deadline per request."""

import asyncio
from dataclasses import dataclass

from gateway_v3 import ask_seller, ms_since
from sellers import BUDGET_MS, SellerError, cheapest
from sellers_net import running_sellers


@dataclass
class Answer:
    best: object
    failed: list  # (seller, exception) pairs
    timed_out: list  # seller names
    ms: int


class Gateway:
    """One per process. Its Semaphore is shared by every request it serves."""

    def __init__(self, ports, max_in_flight=100):
        self.ports = ports
        self.limit = asyncio.Semaphore(max_in_flight)

    async def _ask(self, start, deadline, name, port, item):
        try:
            async with asyncio.timeout_at(deadline):  # waiting for a slot counts too
                async with self.limit:
                    return await ask_seller(start, name, port, item)
        except TimeoutError:
            return TimeoutError(name)
        except (SellerError, OSError) as exc:  # a seller's failure is data, not a crash
            return exc

    async def compare(self, item, budget_ms=BUDGET_MS):
        loop = asyncio.get_running_loop()
        start = loop.time()
        deadline = start + budget_ms / 1000
        async with asyncio.TaskGroup() as tg:
            tasks = {n: tg.create_task(self._ask(start, deadline, n, p, item)) for n, p in self.ports.items()}
        results = {n: t.result() for n, t in tasks.items()}
        offers = [r for r in results.values() if not isinstance(r, Exception)]
        timed_out = [n for n, r in results.items() if isinstance(r, TimeoutError)]
        failed = [(n, r) for n, r in results.items() if isinstance(r, Exception) and n not in timed_out]
        return Answer(cheapest(offers), failed, timed_out, ms_since(start))


def report(a):
    line = (
        f"cheapest: {a.best.seller} at {a.best.price:,} after {a.ms} ms"
        if a.best
        else f"no offer after {a.ms} ms"
    )
    if a.failed:
        line += "; failed: " + ", ".join(f"{n} ({type(e).__name__}: {e})" for n, e in a.failed)
    if a.timed_out:
        line += "; timed out: " + ", ".join(a.timed_out)
    print(line)


async def main():
    with running_sellers() as ports:
        print(f"-- gateway v4: TaskGroup, cap of 100, {BUDGET_MS} ms deadline --")
        report(await Gateway(ports).compare("kettle-1l"))
        print("-- the same, with a cap of 3 calls in flight --")
        report(await Gateway(ports, max_in_flight=3).compare("kettle-1l"))
    with running_sellers(faulty={"seller-c"}) as ports:
        print("-- cap of 100, seller-c failing --")
        report(await Gateway(ports).compare("kettle-1l"))


if __name__ == "__main__":
    asyncio.run(main())

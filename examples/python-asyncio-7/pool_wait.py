"""20 requests at once share a cap of 10 calls. Where the deadline starts decides who waits."""

import asyncio
import contextlib
import io

from gateway_v3 import ask_seller
from gateway_v4 import Gateway
from sellers import SellerError
from sellers_net import running_sellers

REQUESTS, CAP = 20, 10


class TimerAfterTheWait(Gateway):
    """The common mistake: a per-call timeout that starts only once a slot is free."""

    async def _ask(self, start, deadline, name, port, item):
        try:
            async with self.limit:  # may wait here for a long time...
                async with asyncio.timeout(0.25):  # ...and only then start the 250 ms
                    return await ask_seller(start, name, port, item)
        except TimeoutError:
            return TimeoutError(name)
        except (SellerError, OSError) as exc:
            return exc


async def run(gateway_class, ports):
    gateway = gateway_class(ports, max_in_flight=CAP)  # one gateway, one shared cap
    with contextlib.redirect_stdout(io.StringIO()):  # hide the per-seller lines
        async with asyncio.TaskGroup() as tg:
            requests = [tg.create_task(gateway.compare("kettle-1l")) for _ in range(REQUESTS)]
    answers = [r.result() for r in requests]
    slowest = max(a.ms for a in answers)
    late = sum(a.ms > 260 for a in answers)
    empty = sum(a.best is None for a in answers)
    print(
        f"slowest request {slowest:,} ms; over budget: {late} of {REQUESTS}; no offer: {empty} of {REQUESTS}"
    )


async def main():
    with running_sellers() as ports:
        print(f"-- {REQUESTS} requests, cap {CAP}: per-call timeout(0.25) inside the cap --")
        await run(TimerAfterTheWait, ports)
        print(f"-- {REQUESTS} requests, cap {CAP}: gateway v4, timeout_at(deadline) around the wait --")
        await run(Gateway, ports)


if __name__ == "__main__":
    asyncio.run(main())

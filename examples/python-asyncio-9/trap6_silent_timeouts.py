"""Trap 6: timeouts that nobody sees. Three ways a timeout goes missing."""

import asyncio
import contextlib
import io

from gateway_v3 import ask_seller, ms_since
from gateway_v4 import Gateway, report
from metrics import MetricsClient, MetricsSink, outcome
from sellers import SellerError
from sellers_net import running_sellers
from sync_sdk import SyncSellerClient


class Mislabelled(Gateway):
    """A "simplified" handler: every network problem becomes one SellerError."""

    async def _ask(self, start, deadline, name, port, item):
        try:
            async with asyncio.timeout_at(deadline):
                async with self.limit:
                    return await ask_seller(start, name, port, item)
        except (SellerError, OSError) as exc:  # BUG: TimeoutError is an OSError
            return SellerError(f"{name} failed: {exc}")


async def mislabelled(ports):
    sink = MetricsSink()
    metrics = MetricsClient(sink)
    answer = await Mislabelled(ports).compare("kettle-1l")
    report(answer)
    for name in ports:
        await metrics.record(name, outcome(answer, name))
    await metrics.flush()
    print("metrics for seller-e:", {k: v for k, v in sink.totals().items() if "seller-e" in k})


async def partial_answers(ports, requests=10):
    sink = MetricsSink()
    metrics = MetricsClient(sink)
    gateway = Gateway(ports)
    with contextlib.redirect_stdout(io.StringIO()):
        async with asyncio.TaskGroup() as tg:
            calls = [tg.create_task(gateway.compare("kettle-1l")) for _ in range(requests)]
    answers = [c.result() for c in calls]
    winners = {f"{a.best.seller} {a.best.price:,}" for a in answers}
    print(f"{requests} requests answered, every one with: {', '.join(winners)}; errors: 0")
    for answer in answers:
        for name in ports:
            await metrics.record(name, outcome(answer, name))
    await metrics.flush()
    timed_out = sink.totals().get("seller-e timed out", 0)
    print(f"per-seller counts: seller-e timed out on {timed_out} of {requests} requests")
    print(f"the cheapest price, seller-e's 1,149, reached 0 of {requests} shoppers")


async def timer_that_never_fires(ports):
    sdk = SyncSellerClient(ports["seller-e"])
    loop = asyncio.get_running_loop()
    start = loop.time()
    async with asyncio.timeout(0.25) as cm:
        offer = sdk.get_price("kettle-1l")  # a blocking call: the loop never gets a turn
    print(f"no TimeoutError; the block took {ms_since(start)} ms; expired() = {cm.expired()}")
    print(f"and returned an offer: {offer.seller} at {offer.price:,}")


async def main():
    with running_sellers() as ports:
        print("-- 1. except (SellerError, OSError), every problem reported as a SellerError --")
        await mislabelled(ports)
        print("-- 2. partial answers with nothing to show for it --")
        await partial_answers(ports)
        print("-- 3. asyncio.timeout(0.25) around a blocking call --")
        await timer_that_never_fires(ports)


if __name__ == "__main__":
    asyncio.run(main())

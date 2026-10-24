"""Rung 4: four numbers that are true and still mislead, each next to the number that does not."""

import asyncio
import logging

from gateway_v9 import Budget
from observe import Histogram, json_lines
from stubs import StallingAuditStore, StubSellers, make_gateway
from virtual_clock import VirtualClockLoop


def averages_hide_the_tail():
    h = Histogram()
    for _ in range(985):
        h.observe(250)  # answered at the budget
    for _ in range(15):
        h.observe(2250)  # 15 in 1,000 waited 2 s more for a stuck audit row
    print("1. 1,000 requests: 985 at 250 ms, 15 at 2,250 ms")
    print(f"   mean {h.mean():.0f} ms; p50 <= {h.quantile(0.5)} ms; p99 <= {h.quantile(0.99)} ms")


class FlakySellerC(StubSellers):
    """seller-c hangs on 3 calls in 10: a seller having a bad day."""

    async def ask(self, name, item):
        if name == "seller-c" and int(item.split("-")[1]) % 10 < 3:
            await asyncio.Event().wait()
        return await super().ask(name, item)


async def only_the_survivors():
    caps = {"seller-a": 10, "seller-b": 10, "seller-c": 100, "seller-d": 10, "seller-e": 4}
    gateway = make_gateway(FlakySellerC(), caps=caps)  # room for every seller-c call: no line, no skips
    await gateway.start()
    for n in range(100):  # 100 different items: no cache hits, one call per seller each
        await gateway.compare(f"item-{n}")
    await asyncio.sleep(2.0)  # the hanging calls end at their own 2 s deadline
    await gateway.shutdown([], Budget())
    return gateway.seller_ms["seller-c"], gateway.seller_outcomes


def survivors():
    lines = json_lines("gateway")
    every_call, outcomes = asyncio.run(only_the_survivors(), loop_factory=VirtualClockLoop)
    answered = Histogram()  # what a histogram fed only on success would hold
    for event in lines.events():
        if (
            event["event"] == "seller call"
            and event["seller"] == "seller-c"
            and event["outcome"] == "answered"
        ):
            answered.observe(event["ms"])
    counts = {k.split(" ", 1)[1]: v for k, v in sorted(outcomes.items()) if k.startswith("seller-c")}
    print("2. seller-c on a bad day: 100 requests for 100 items; 3 calls in 10 hang until the 2 s deadline")
    print(f"   answered calls only: {answered.count} calls, p99 <= {answered.quantile(0.99)} ms")
    print(f"   every call: {every_call.count} calls, p99 <= {every_call.quantile(0.99)} ms; {counts}")


async def stalled_audit():
    store = StallingAuditStore()
    gateway = make_gateway(store=store)
    await gateway.start()
    store.answering.clear()
    answer = await gateway.handle("shop-1", "kettle-1l", asyncio.get_running_loop().time())
    store.answering.set()
    await gateway.shutdown([], Budget())
    return answer.ms, gateway.request_ms.sum


def wrong_start_point():
    answer_ms, request_ms = asyncio.run(stalled_audit(), loop_factory=VirtualClockLoop)
    print("3. one request while the audit store is stalled")
    print(f"   Answer.ms (compare() alone): {answer_ms} ms; the shopper waited: {request_ms:.0f} ms")


def averaged_lag():
    samples = [0.0] * 1199 + [300.0]  # one minute of 50 ms samples, one 300 ms stall
    print("4. loop lag over one minute: 1,200 samples, one 300 ms stall")
    print(f"   average {sum(samples) / len(samples):.2f} ms; worst {max(samples):.0f} ms")


logging.getLogger("gateway").addHandler(logging.NullHandler())
averages_hide_the_tail()
survivors()
wrong_start_point()
averaged_lag()

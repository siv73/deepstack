"""When does an abandoned async generator clean up? Three quick quotes for kettle-1l, each stopping
at seller-b's 1,199 (the first offer at or below 1,200), with the asks as stand-in timers."""

import asyncio
import contextlib
import logging

from offer_stream import offers
from request_log import RequestIdFilter, request_id
from sellers import SELLERS, Offer

PORTS = {s.name: None for s in SELLERS}  # stand-in sellers need no ports
LATENCY = {s.name: s.latency_ms / 1000 for s in SELLERS}
PRICE = {s.name: s.price for s in SELLERS}
kept = []  # what a debugging aid might hold on to
start = 0.0


def now():
    return round((asyncio.get_running_loop().time() - start) * 100) * 10


class Timeline(logging.Handler):
    """Prints each log record at once, with the time, the Task that wrote it and its request id."""

    def __init__(self):
        super().__init__()
        self.addFilter(RequestIdFilter())

    def emit(self, record):
        task = asyncio.current_task()
        where = task.get_name() if task else "no Task"
        print(f"{now():4} ms [{record.request_id}] in {where}: {record.getMessage()}")


log = logging.getLogger("gateway")
log.setLevel(logging.INFO)
log.addHandler(Timeline())
log.propagate = False


def say(text):
    print(f"{now():4} ms [{request_id.get()}] in {asyncio.current_task().get_name()}: {text}")


async def ask(name, port):
    await asyncio.sleep(LATENCY[name])
    return Offer(name, PRICE[name])


async def first_good(stream):
    async for offer in stream:
        if offer.price <= 1200:
            return offer  # leaves the async for early


async def quote(how):
    request_id.set(f"quick-{how}")
    stream = offers(ask, PORTS, "kettle-1l")
    if how == "aclosing":
        async with contextlib.aclosing(stream) as s:
            offer = await first_good(s)
    else:
        if how == "kept":
            kept.append(stream)
        offer = await first_good(stream)
    waiting = sum(1 for t in asyncio.all_tasks() if t.get_name().startswith("ask ") and not t.done())
    say(f"answered {offer.seller} {offer.price:,}; asks still waiting: {waiting}")


async def main():
    global start
    start = asyncio.get_running_loop().time()
    for how in ("left open", "aclosing", "kept"):
        print(f"-- {how} --")
        await asyncio.create_task(quote(how), name=f"request {how}")
        await asyncio.sleep(0.05)  # what happens to the stream after the request returned
    print("-- main() returns; asyncio.run shuts down --")


asyncio.run(main())
print("asyncio.run returned")

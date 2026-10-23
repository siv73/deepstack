"""Gateway v9: gateway v8 that stops well, plus a quick quote read from an async generator.

New on this page: SIGTERM starts shutdown() instead of killing the process. shutdown() stops
accepting, drains the requests in flight within a deadline, cancels the rest, waits a bounded
time for single-flight fills, stops seller-e's feed thread, flushes the audit queue and the
metrics, and only then lets asyncio.run close the loop. Every step has its own time limit.
A second port answers quick quotes: the first offer at or below `good_enough`, read from
offer_stream.offers() inside contextlib.aclosing().
"""

import asyncio
import contextlib
import contextvars
import io
import signal
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass

import gateway_v8
from audit import AuditStore
from gateway_v3 import ms_since
from gateway_v5 import Answer
from gateway_v6 import describe
from metrics import MetricsClient, MetricsSink
from offer_stream import offers
from price_feed import PriceFeed
from ratelimit import TokenBucket
from request_log import request_id
from scoring import score_offers
from sellers import BUDGET_MS, Offer
from sellers_net import running_sellers

quote_mode = contextvars.ContextVar("quote_mode", default="full")


@dataclass
class Budget:
    """Seconds for each shutdown step. Production values are on the page; these are scaled."""

    drain: float = 1.0  # requests in flight finish
    cancel: float = 0.2  # requests still running after the drain unwind
    fills: float = 1.0  # single-flight fills finish and are cached
    feed: float = 0.5  # seller-e's feed thread stops
    flush: float = 0.5  # audit rows and metrics are written


class StoppableFeed(PriceFeed):
    """Page 7's feed with a stop button: a normal (not daemon) thread that ends when asked."""

    def __init__(self, changes):
        super().__init__(changes)
        self.stopped = threading.Event()

    def subscribe(self, callback):
        def run():
            for at, item, price in self.changes:
                if self.stopped.wait(at):  # sleep `at` seconds, or wake at once if stopped
                    return
                self.acks.append(callback(item, Offer("seller-e", price)))

        self.thread = threading.Thread(target=run, name="seller-e-feed")  # not a daemon
        self.thread.start()

    def stop(self):
        self.stopped.set()


class Gateway(gateway_v8.Gateway):
    def __init__(self, *args, good_enough=1200, **kwargs):
        super().__init__(*args, **kwargs)
        self.good_enough = good_enough
        self.requests = set()  # request Tasks in progress: shutdown waits for, then cancels, these
        self.draining = False
        self.stopped_by_shutdown = 0  # a metric, kept apart from hang-ups
        self.feed = None

    async def start(self):
        await super().start()
        self.idle = asyncio.Event()  # created on the loop that uses it (Part 7)
        self.idle.set()

    async def serve(self, reader, writer):
        if self.draining:  # accepted just before the listener closed: say so, do no work
            await reader.readline()
            writer.write(b"busy\n")
            writer.close()
            return
        me = asyncio.current_task()
        self.requests.add(me)
        self.idle.clear()
        try:
            await super().serve(reader, writer)  # gateway v7's door, v6's hang-up watch, v8's handle()
        finally:
            self.requests.discard(me)
            if not self.requests:
                self.idle.set()

    async def serve_quick(self, reader, writer):
        quote_mode.set("quick")  # this connection's Task only (Part 7): compare() reads it
        await self.serve(reader, writer)

    async def handle(self, shopper, item, start):
        request_id.set(shopper)
        try:
            answer = await self.compare(item)
        except asyncio.CancelledError:
            if self.draining:  # our own cancel, not the shopper's: count and label it apart
                self.stopped_by_shutdown += 1
                await self._audit(f"{shopper} {item}: stopped by shutdown after {ms_since(start)} ms")
            else:
                self.hung_up += 1
                await self._audit(f"{shopper} {item}: hung up after {ms_since(start)} ms")
            raise
        await self._audit(f"{shopper} {item}: {describe(answer)}")
        gateway_v8.log.info("answered %s", describe(answer))
        return answer

    async def compare(self, item):
        if quote_mode.get() == "quick":
            return await self.quick(item)
        return await super().compare(item)

    async def quick(self, item):
        """The first offer at or below good_enough, or the best one by the deadline."""
        loop = asyncio.get_running_loop()
        start = loop.time()
        deadline = start + BUDGET_MS / 1000

        def ask(name, port):
            return self._ask(start, deadline, name, port, item)  # v8: cache, then a shared fill

        best = None
        async with contextlib.aclosing(offers(ask, self.ports, item)) as stream:
            async for offer in stream:
                if best is None or offer.price < best.price:
                    best = offer
                if offer.price <= self.good_enough:
                    break  # leaving early: aclosing() runs the stream's finally here, in this Task
        return Answer(best, [], [], ms_since(start), partial=True)

    async def shutdown(self, servers, budget):
        """Stop in order, each step with its own time limit. Returns one report line per step."""
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        report = []

        def note(text):
            report.append(f"{round((loop.time() - t0) * 100) * 10:5} ms  {text}")

        self.draining = True
        for server in servers:
            server.close()  # 1. stop accepting: listening sockets closed, open connections kept
        note(f"listeners closed; {len(self.requests)} requests in flight")

        try:  # 2. drain: let requests in flight finish, up to budget.drain
            async with asyncio.timeout(budget.drain):
                await self.idle.wait()
            note("drained: no request left in flight")
        except TimeoutError:
            note(f"drain deadline: {len(self.requests)} requests still running")

        left = list(self.requests)  # 3. cancel the rest, and give their clean-up a moment
        for task in left:
            task.cancel("shutdown")
        if left:
            await asyncio.wait(left, timeout=budget.cancel)
            note(f"cancelled {len(left)} requests; {sum(not t.done() for t in left)} still unwinding")

        fills = list(self.flights.flights.values())  # 4. owned work: fills that serve later requests
        if fills:
            _, late = await asyncio.wait(fills, timeout=budget.fills)
            for task in late:
                task.cancel()
            note(f"fills: {len(fills) - len(late)} finished, {len(late)} cancelled")

        if self.feed is not None:  # 5. seller-e's feed thread, while the loop can still answer it
            self.feed.stop()
            await asyncio.to_thread(self.feed.thread.join, budget.feed)
            note(f"feed thread stopped: alive = {self.feed.thread.is_alive()}")

        try:  # 6. audit rows and metrics: v7's stop() closes the audit queue, v5's flushes metrics
            async with asyncio.timeout(budget.flush):
                await self.stop()
            note(f"audit queue flushed: {len(self.audit_queue.store.rows)} rows written")
        except TimeoutError:
            note(f"flush deadline: {self.audit_queue.queue.qsize()} rows not written")
        return report


def build(ports, sdk_pool, cpu_pool, store, cls=None):
    return (cls or Gateway)(
        ports,
        sdk_pool,
        cpu_pool,
        MetricsClient(MetricsSink()),
        audit=store,
        max_requests=200,
        caps={"seller-a": 10, "seller-b": 10, "seller-c": 3, "seller-d": 10, "seller-e": 4},
        max_waiting={"seller-a": 10, "seller-b": 10, "seller-c": 2, "seller-d": 10, "seller-e": 0},
        rates={"seller-d": TokenBucket(rate=20, burst=5)},
        writers=50,
        ttl=30.0,
    )


def say(text):
    print(text, file=sys.__stdout__, flush=True)  # the report; the seller calls' own lines are hidden


async def run(ports, sdk_pool, cpu_pool, budget):
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop.set)  # a callback on the loop, not a kill
    loop.add_signal_handler(signal.SIGINT, stop.set)
    store = AuditStore()
    gateway = build(ports, sdk_pool, cpu_pool, store)
    await gateway.start()
    servers = [
        await asyncio.start_server(gateway.serve, "127.0.0.1", 0),
        await asyncio.start_server(gateway.serve_quick, "127.0.0.1", 0),
    ]
    gateway.feed = StoppableFeed([(0.2, "toaster-2s", 1059)] * 50)  # a change every 200 ms
    gateway.feed.subscribe(gateway.on_price_change)
    say("ready " + " ".join(str(s.sockets[0].getsockname()[1]) for s in servers))
    await stop.wait()
    say("SIGTERM: shutdown starts")
    for line in await gateway.shutdown(servers, budget):
        say(line)
    say(f"audit rows: {len(store.rows)}, lost: {len(store.lost)}; stopped: {gateway.stopped_by_shutdown}")


def main():
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
        contextlib.redirect_stdout(io.StringIO()),
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))  # start the worker processes before the loop runs
        asyncio.run(run(ports, sdk_pool, cpu_pool, Budget()))
    say("exit 0")


if __name__ == "__main__":
    main()

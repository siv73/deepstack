"""Gateway v8: gateway v7 with a shared price cache, request ids that follow the work, and a thread bridge.

New on this page: each (seller, item) price is cached for `ttl` seconds and filled by one
single-flight call, however many requests ask at once; the fill runs as an owned Task in its own
context, with its own deadline, so one request's deadline or hang-up never cuts it. The request
id is a ContextVar set in handle(); every log line reads it, and seller-e's SDK thread gets it
through copy_context().run. seller-e's price feed calls back on its own thread, and reaches the
loop with run_coroutine_threadsafe().
"""

import asyncio
import contextlib
import contextvars
import functools
import io
import logging
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v7
from audit import AuditStore
from limits import Skipped
from metrics import MetricsClient, MetricsSink
from price_cache import PriceCache
from price_feed import PriceFeed
from ratelimit import TokenBucket
from request_log import capture, request_id
from scoring import score_offers
from sellers import SellerError
from sellers_net import running_sellers
from single_flight import SingleFlight
from spawn import failures

log = logging.getLogger("gateway")


class Gateway(gateway_v7.Gateway):
    def __init__(self, *args, ttl=30.0, fill_s=2.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache, self.flights, self.fill_s = PriceCache(ttl), SingleFlight(), fill_s
        self.seller_calls = Counter()  # calls actually made to each seller: a metric
        self.loop = None

    async def start(self):
        await super().start()
        self.loop = asyncio.get_running_loop()  # threads need it to reach the loop

    async def handle(self, shopper, item, start):
        request_id.set(shopper)  # once, at the edge: every Task and copy made from here carries it
        answer = await super().handle(shopper, item, start)
        log.info("answered %s", gateway_v7.gateway_v6.describe(answer))
        return answer

    async def _ask(self, start, deadline, name, port, item):
        offer = self.cache.get(name, item)
        if offer is not None:
            return offer  # fresh: no seller call
        make_call = functools.partial(self._fill, name, port, item)
        fill = self.flights.start((name, item), make_call, name=f"fill {name} {item}")
        self.waiting += 1
        try:
            async with asyncio.timeout_at(deadline):
                return await asyncio.shield(fill)  # our deadline or hang-up cuts our wait, never the fill
        except TimeoutError:
            return TimeoutError(name)
        finally:
            self.waiting -= 1

    async def _fill(self, name, port, item):
        """The one call for (seller, item): its own context, its own deadline; failures are values."""
        request_id.set(f"fill {name} {item}")
        loop = asyncio.get_running_loop()
        start = loop.time()
        deadline = start + self.fill_s
        self.seller_calls[name] += 1
        log.info("calling %s", name)
        try:
            async with asyncio.timeout_at(deadline):
                offer = await self.limits.call(name, lambda: self._call_by(deadline, start, name, port, item))
        except TimeoutError:
            return TimeoutError(name)
        except (Skipped, SellerError, OSError) as exc:
            return exc  # not cached: the next request tries again
        self.cache.put(name, item, offer)
        log.info("%s answered %s", name, offer.price)
        return offer

    async def _call_by(self, deadline, start, name, port, item):
        if name != "seller-e":
            return await super()._call_by(deadline, start, name, port, item)
        loop = asyncio.get_running_loop()
        left = max(deadline - loop.time(), 0.001)  # Part 5: the deadline passed down
        call = functools.partial(self.sdk.get_price, item, timeout=left)
        ctx = contextvars.copy_context()  # and now the context too: the SDK's logs carry this fill's id
        return await loop.run_in_executor(self.sdk_pool, functools.partial(ctx.run, call))

    def on_price_change(self, item, offer):
        """Called by seller-e's feed on the feed's own thread. Returns once the change is applied."""
        future = asyncio.run_coroutine_threadsafe(self.apply_price_change(item, offer), self.loop)
        return future.result(timeout=1.0)  # the feed's thread waits; the loop does not

    async def apply_price_change(self, item, offer):
        request_id.set(f"feed {offer.seller}")
        self.cache.put(offer.seller, item, offer)
        await self._audit(f"feed: {offer.seller} {item} now {offer.price:,}")
        log.info("price change applied: %s %s", item, offer.price)
        return "applied"


async def crowd(port, shoppers, label, item="kettle-1l"):
    """`shoppers` connect, wait at a Barrier, then all send at once. Returns a summary line."""
    loop = asyncio.get_running_loop()
    gate = asyncio.Barrier(shoppers)
    start = None

    async def one(n):
        nonlocal start
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        if await gate.wait() == 0:
            start = loop.time()  # the moment the last shopper arrived and all were released
        writer.write(f"{label}-{n} {item}\n".encode())
        await writer.drain()
        line = (await reader.readline()).decode().strip()
        writer.close()
        await writer.wait_closed()
        return line, loop.time()

    async with asyncio.TaskGroup() as tg:
        replies = [tg.create_task(one(n)) for n in range(1, shoppers + 1)]
    replies = [r.result() for r in replies]
    answers = dict(Counter(line for line, _ in replies))
    last = round((max(t for _, t in replies) - start) * 100) * 10
    return f"  {shoppers} answered {answers}, the last after {last} ms"


async def serve(ports, sdk_pool, cpu_pool, store):
    lines = capture("gateway", "seller_e_sdk")
    gateway = Gateway(
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
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    out = []

    def calls_made():
        made = dict(sorted(gateway.seller_calls.items())) or "none"
        gateway.seller_calls.clear()
        return f"  seller calls made: {made}"

    with contextlib.redirect_stdout(io.StringIO()):  # the seller calls' own lines are not the report
        async with server:
            out.append("-- 100 shoppers at once, kettle-1l, empty cache --")
            out += [await crowd(port, 100, "sale"), calls_made()]
            await asyncio.sleep(1.0)  # seller-e's fill, never cut by any request, lands at about 900 ms
            out.append("-- 10 shoppers, 1 s later --")
            out += [await crowd(port, 10, "later"), calls_made()]
            out.append("-- seller-e's feed pushes kettle-1l at 1,099 from its own thread --")
            feed = PriceFeed([(0.05, "kettle-1l", 1099)])
            feed.subscribe(gateway.on_price_change)
            await asyncio.to_thread(feed.join, 2.0)
            out.append(f"  the feed's callback returned {feed.acks}")
            out += [await crowd(port, 1, "after-feed"), calls_made()]
            out.append("-- one shopper asks for toaster-2s; the gateway stops right after --")
            out.append(await crowd(port, 1, "last", item="toaster-2s"))
            in_flight = list(gateway.flights.flights.values())
            await gateway.stop()
    print("\n".join(out))
    print(f"  fills still in flight when stop() returned: {[t.get_name() for t in in_flight]}")
    kinds = Counter(kind(line[1 : line.index("]")]) for line in lines.lines)
    print(f"log lines, by whose id they carry: {dict(sorted(kinds.items()))}")
    for line in lines.lines:
        if line.startswith(("[sale-7]", "[fill seller-e kettle", "[feed")):
            print(f"  {line}")
    print(f"audit rows written: {len(store.rows)} | background failures: {dict(failures) or 'none'}")
    return in_flight


def kind(rid):
    """'sale-7' -> 'sale-*'; 'fill seller-e kettle-1l' -> 'fill'; 'feed seller-e' -> 'feed'."""
    return rid.split(" ")[0] if " " in rid else rid.rsplit("-", 1)[0] + "-*"


def main():
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))  # start the worker processes before the loop runs
        in_flight = asyncio.run(serve(ports, sdk_pool, cpu_pool, AuditStore()))
    for task in in_flight:  # asyncio.run cancelled every Task still running when serve() returned
        print(f"after asyncio.run returned: {task.get_name()} cancelled = {task.cancelled()}")


if __name__ == "__main__":
    main()

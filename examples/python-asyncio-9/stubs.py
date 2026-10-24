"""Stub sellers and pools for tests: the gateway's real code, with nothing outside the process.

StubSellers answers from a table instead of a socket. A seller can be made to fail or to hang.
TestGateway is gateway v10 with one method replaced: _call_by(), the single place every seller
call goes through (v6 and v8), now asks the stubs. InlineExecutor runs the ranking step in the
caller instead of a process pool. FakeConnection is a shopper's TCP connection without a socket.
"""

import asyncio
import concurrent.futures

import gateway_v10
from audit import AuditStore
from metrics import MetricsClient, MetricsSink
from ratelimit import TokenBucket
from sellers import SELLERS, Offer, SellerError

PORTS = {s.name: None for s in SELLERS}  # names only: no seller listens anywhere


class StubSellers:
    def __init__(self, latency_ms=None, price=None):
        self.latency_ms = {s.name: s.latency_ms for s in SELLERS} | (latency_ms or {})
        self.price = {s.name: s.price for s in SELLERS} | (price or {})
        self.failing, self.hanging = set(), set()
        self.calls = []  # (seller, item) in the order they were made

    async def ask(self, name, item):
        self.calls.append((name, item))
        if name in self.hanging:
            await asyncio.Event().wait()  # never answers; only a deadline or a cancel ends this
        await asyncio.sleep(self.latency_ms[name] / 1000)
        if name in self.failing:
            raise SellerError(f"{name} failed")
        return Offer(name, self.price[name])


class InlineExecutor(concurrent.futures.Executor):
    """run_in_executor() with no thread or process: the function runs at once, in the caller."""

    def submit(self, fn, /, *args, **kwargs):
        future = concurrent.futures.Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class StallingAuditStore(AuditStore):
    """A store that can stop answering (a database whose connection hangs) and start again."""

    def __init__(self, ms=20):
        super().__init__(ms)
        self.answering = asyncio.Event()
        self.answering.set()

    async def write(self, row):
        await self.answering.wait()  # stopped: the INSERT never comes back
        await super().write(row)


class TestGateway(gateway_v10.Gateway):
    __test__ = False  # a helper, not a pytest test class

    def __init__(self, *args, stubs, **kwargs):
        super().__init__(*args, **kwargs)
        self.stubs = stubs

    async def _call_by(self, deadline, start, name, port, item):
        return await self.stubs.ask(name, item)


def make_gateway(stubs=None, store=None, **overrides):
    """Gateway v10 as production builds it (v9's limits), with stub sellers and inline pools."""
    settings = dict(
        audit=store if store is not None else AuditStore(),
        max_requests=200,
        caps={"seller-a": 10, "seller-b": 10, "seller-c": 3, "seller-d": 10, "seller-e": 4},
        max_waiting={"seller-a": 10, "seller-b": 10, "seller-c": 2, "seller-d": 10, "seller-e": 0},
        rates={"seller-d": TokenBucket(rate=20, burst=5)},
        writers=50,
        ttl=30.0,
    )
    settings.update(overrides)
    pool = InlineExecutor()
    return TestGateway(
        PORTS, pool, pool, MetricsClient(MetricsSink()), stubs=stubs or StubSellers(), **settings
    )


class FakeWriter:
    """The parts of asyncio.StreamWriter the gateway uses, writing into a list."""

    def __init__(self):
        self.sent, self.closed = [], False

    def write(self, data):
        self.sent.append(data.decode())

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass

    def is_closing(self):
        return self.closed


def connection(line):
    """A shopper who sent `line` and keeps the connection open: (reader, writer) for serve()."""
    reader = asyncio.StreamReader()
    reader.feed_data(f"{line}\n".encode())  # no EOF: the hang-up watch waits, as for a real shopper
    return reader, FakeWriter()


def hang_up(reader):
    """The shopper closes the connection: the hang-up watch's read(1) returns."""
    reader.feed_eof()

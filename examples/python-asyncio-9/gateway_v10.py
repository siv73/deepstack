"""Gateway v10: gateway v9 that can be seen from outside, and tested without real time.

New on this page: loop lag as a metric; a latency histogram and outcome counts for every seller
call; one JSON log line per request and per seller call, each carrying the request id; request
Tasks named after the shopper and item, so task dumps and `python -m asyncio ps` are readable;
a deadline on waiting for the audit row, so a stuck audit store shows up as a count and a log
line instead of requests that never answer; and dump_tasks() on SIGUSR1.
Nothing here changes what the gateway answers.
"""

import asyncio
import logging
import signal
from collections import Counter

import gateway_v9
from gateway_v3 import ms_since
from limits import Skipped
from observe import Histogram, LagMonitor, dump_tasks, fields

log = logging.getLogger("gateway")


def outcome_of(result):
    if isinstance(result, TimeoutError):
        return "timed out"
    if isinstance(result, Skipped):
        return "skipped"
    if isinstance(result, BaseException):
        return "failed"
    return "answered"


class Gateway(gateway_v9.Gateway):
    def __init__(self, *args, audit_s=1.0, lag_every=0.05, **kwargs):
        super().__init__(*args, **kwargs)
        self.audit_s = audit_s  # longest a request waits for its audit row
        self.lag = LagMonitor(lag_every)
        self.seller_ms = {name: Histogram() for name in self.ports}  # every seller call, any outcome
        self.seller_outcomes = Counter()  # "seller-e timed out": calls, not requests
        self.request_ms = Histogram()  # answered requests, from the line arriving to the answer
        self.request_outcomes = Counter()  # "answered", "partial", "hung up", "stopped by shutdown"
        self.audit_timeouts = 0

    async def start(self):
        await super().start()
        self.lag.start()

    async def stop(self):
        await self.lag.stop()
        await super().stop()

    async def handle(self, shopper, item, start):
        asyncio.current_task().set_name(f"{shopper} {item}")  # what dumps and ps print
        try:
            answer = await super().handle(shopper, item, start)  # v9: sets the request id, audits
        except asyncio.CancelledError:
            how = "stopped by shutdown" if self.draining else "hung up"
            self.request_outcomes[how] += 1
            log.warning("request cancelled", extra=fields(item=item, how=how, ms=ms_since(start)))
            raise
        kind = "partial" if answer.partial else "answered"
        self.request_outcomes[kind] += 1
        self.request_ms.observe(ms_since(start))
        best = f"{answer.best.seller} {answer.best.price}" if answer.best else None
        log.info(
            "request done",
            extra=fields(
                item=item, best=best, ms=ms_since(start), timed_out=answer.timed_out, partial=answer.partial
            ),
        )
        return answer

    async def _fill(self, name, port, item):
        loop = asyncio.get_running_loop()
        start = loop.time()
        result = "cancelled"
        try:
            result = await super()._fill(name, port, item)  # v8: the one call for (seller, item)
            return result
        finally:
            ms = round((loop.time() - start) * 1000)
            outcome = result if isinstance(result, str) else outcome_of(result)
            self.seller_ms[name].observe(ms)
            self.seller_outcomes[f"{name} {outcome}"] += 1
            log.info("seller call", extra=fields(seller=name, item=item, outcome=outcome, ms=ms))

    async def _audit(self, row):
        try:
            async with asyncio.timeout(self.audit_s):
                await super()._audit(row)  # v6: an owned write behind shield(); v7: through the queue
        except TimeoutError:  # the write itself goes on (it is shielded); this request stops waiting
            self.audit_timeouts += 1
            log.warning("audit row not confirmed", extra=fields(waited_ms=round(self.audit_s * 1000)))

    def snapshot(self):
        """What a metrics scrape would read: counts and histogram summaries, in plain numbers."""
        return {
            "loop lag worst ms": round(self.lag.take_worst()),
            "requests": dict(sorted(self.request_outcomes.items())),
            "request ms p50/p99": (self.request_ms.quantile(0.5), self.request_ms.quantile(0.99)),
            "seller calls": dict(sorted(self.seller_outcomes.items())),
            "audit timeouts": self.audit_timeouts,
            "requests in flight": len(self.requests),
        }


def install_dump_on_sigusr1(file=None):
    """kill -USR1 <pid> prints every Task and where it waits: the in-process view, on any version."""
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGUSR1, lambda: dump_tasks(file) if file else dump_tasks())


def build(ports, sdk_pool, cpu_pool, store, cls=None, **extra):
    gateway = gateway_v9.build(ports, sdk_pool, cpu_pool, store, cls=cls or Gateway)
    for key, value in extra.items():
        setattr(gateway, key, value)
    return gateway

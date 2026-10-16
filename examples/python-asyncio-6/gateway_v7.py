"""Gateway v7: gateway v6 that bounds its work and refuses what it cannot finish.

New on this page: the front door refuses a request at once ("busy", the line protocol's 503)
when max_requests are already in progress. Each seller has its own cap and a bounded line
for that cap; seller-d also has a rate limit. Audit rows go through a bounded queue to a
fixed pool of writers, so a slow audit store slows the requests instead of piling up Tasks.
"""

import asyncio
import contextlib
import io
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v6
from audit import AuditStore
from audit_queue import AuditQueue
from limits import SellerLimits, Skipped
from metrics import MetricsClient, MetricsSink
from ratelimit import TokenBucket
from scoring import score_offers
from sellers_net import running_sellers
from spawn import failures


class Gateway(gateway_v6.Gateway):
    def __init__(self, *args, audit, max_requests, caps, max_waiting, rates, writers=4, **kwargs):
        self.audit_queue = AuditQueue(audit, writers=writers)
        super().__init__(*args, audit=self.audit_queue, **kwargs)  # v6's _audit() now writes through it
        self.max_requests, self.in_progress, self.refused = max_requests, 0, 0
        self.limits = SellerLimits(caps, max_waiting, rates)  # replaces v4's one shared cap

    async def start(self):
        await super().start()
        self.audit_queue.start()

    async def stop(self):
        await self.audit_queue.close()  # finish every queued row, then the writers end
        await super().stop()

    async def serve(self, reader, writer):
        if self.in_progress >= self.max_requests:  # full: say so before doing any work
            self.refused += 1
            await reader.readline()  # read the request, so closing does not reset the connection
            writer.write(b"busy\n")  # the line protocol's 503
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
            return
        self.in_progress += 1  # no await between the check and this line
        try:
            await super().serve(reader, writer)  # gateway v6, unchanged
        finally:
            self.in_progress -= 1

    async def _ask(self, start, deadline, name, port, item):
        self.waiting += 1
        try:
            async with asyncio.timeout_at(deadline):  # the wait in this seller's line counts too
                return await self.limits.call(name, lambda: self._call_by(deadline, start, name, port, item))
        except TimeoutError:
            return TimeoutError(name)
        except (Skipped, gateway_v6.SellerError, OSError) as exc:
            return exc
        finally:
            self.waiting -= 1


async def crowd(port, shoppers, label):
    """Send `shoppers` requests at once. Returns a summary of the replies."""
    loop = asyncio.get_running_loop()
    start = loop.time()

    async def one(n):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(f"{label}-{n} kettle-1l\n".encode())
        await writer.drain()
        line = (await reader.readline()).decode().strip()
        writer.close()
        await writer.wait_closed()
        return line, round((loop.time() - start) * 100) * 10

    async with asyncio.TaskGroup() as tg:
        replies = [tg.create_task(one(n)) for n in range(shoppers)]
    replies = [r.result() for r in replies]
    busy = [ms for line, ms in replies if line == "busy"]
    served = [(line, ms) for line, ms in replies if line != "busy"]
    lines = []
    if served:
        answers = dict(Counter(line for line, _ in served))
        lines.append(f"  {len(served)} answered {answers}, the last after {max(ms for _, ms in served)} ms")
    if busy:
        lines.append(f"  {len(busy)} told 'busy', the last after {max(busy)} ms")
    return "\n".join(lines)


async def serve(ports, sdk_pool, cpu_pool, store):
    gateway = Gateway(
        ports,
        sdk_pool,
        cpu_pool,
        MetricsClient(MetricsSink()),
        audit=store,
        max_requests=10,  # requests in progress at once; the 11th is told "busy"
        caps={"seller-a": 10, "seller-b": 10, "seller-c": 3, "seller-d": 10, "seller-e": 4},
        max_waiting={"seller-a": 10, "seller-b": 10, "seller-c": 2, "seller-d": 10, "seller-e": 0},
        rates={"seller-d": TokenBucket(rate=20, burst=5)},  # seller-d's contract: 20 calls/s
        writers=2,
    )
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    out = []  # the report; printed at the end, because the sellers' answer lines are hidden
    with contextlib.redirect_stdout(io.StringIO()):
        async with server:
            out.append("-- 30 shoppers at once; room for 10 requests --")
            out.append(await crowd(port, 30, "sale"))
            skipped = dict(sorted(gateway.limits.skipped.items()))
            out.append(f"  refused at the door: {gateway.refused}; seller calls not made: {skipped}")
            await asyncio.sleep(1.0)  # seller-e's threads finish; seller-d's tokens refill
            gateway.refused = 0
            store.ms = 200  # the audit store slows down: 200 ms a write, 2 writers
            out.append("-- audit store at 200 ms a write: 10 shoppers, 10 more at 300 ms --")
            early = asyncio.create_task(crowd(port, 10, "early"))
            await asyncio.sleep(0.3)
            out.append(
                f"  at 300 ms: {gateway.in_progress} requests in progress, "
                f"{gateway.audit_queue.queue.qsize()} rows in the audit queue"
            )
            late = await crowd(port, 10, "late")
            out += [await early, late]
        await gateway.stop()
    print("\n".join(out))
    print("audit rows written:", len(store.rows), "| background failures:", dict(failures) or "none")


def main():
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))  # start the worker processes before the loop runs
        asyncio.run(serve(ports, sdk_pool, cpu_pool, AuditStore()))


if __name__ == "__main__":
    main()

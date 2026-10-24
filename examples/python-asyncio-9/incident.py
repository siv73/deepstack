"""The incident this page starts from: the audit store stops answering, and requests stop answering too.

stuck(...) runs a gateway (v9 by default) on real sockets with real seller stubs, sends 5
shoppers while the audit store works, then stops the store and sends 5 more, each willing to
wait `patience` seconds. While those 5 wait, it calls `look(gateway)`: whatever the program
wants to inspect. Then it lets the store answer again, so every request can finish.
"""

import asyncio
import contextlib
import io
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v9
from metrics import MetricsClient, MetricsSink
from ratelimit import TokenBucket
from scoring import score_offers
from sellers_net import running_sellers
from stubs import StallingAuditStore


async def shopper(port, name, item, patience):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"{name} {item}\n".encode())
    await writer.drain()
    try:
        async with asyncio.timeout(patience):
            return (await reader.readline()).decode().strip()
    except TimeoutError:
        return f"no answer after {round(patience * 1000):,} ms"
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


def make(cls, ports, sdk_pool, cpu_pool, store, **extra):
    return cls(
        ports,
        sdk_pool,
        cpu_pool,
        MetricsClient(MetricsSink()),
        audit=store,
        max_requests=200,
        caps={"seller-a": 10, "seller-b": 10, "seller-c": 3, "seller-d": 10, "seller-e": 4},
        max_waiting={"seller-a": 10, "seller-b": 10, "seller-c": 2, "seller-d": 10, "seller-e": 0},
        rates={"seller-d": TokenBucket(rate=20, burst=5)},
        writers=2,
        ttl=30.0,
        **extra,
    )


async def run(ports, sdk_pool, cpu_pool, look, cls, patience, item_after, **extra):
    store = StallingAuditStore()
    gateway = make(cls, ports, sdk_pool, cpu_pool, store, **extra)
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    report = []
    with contextlib.redirect_stdout(io.StringIO()):  # the seller calls' own lines are not the report
        async with server:
            before = await asyncio.gather(*(shopper(port, f"shop-{n}", "kettle-1l", 2) for n in range(1, 6)))
            report.append(f"5 shoppers, audit store working: {dict(Counter(before))}")
            store.answering.clear()  # the audit store stops answering
            waiting = [
                asyncio.create_task(shopper(port, f"shop-{n}", item_after, patience), name=f"shopper {n}")
                for n in range(6, 11)
            ]
            await asyncio.sleep(patience / 2)  # the 5 are waiting now
            seen = await look(gateway)
            after = await asyncio.gather(*waiting)
            report.append(f"5 shoppers, audit store stopped: {dict(Counter(after))}")
            store.answering.set()  # the store answers again; the stuck requests can finish
            await asyncio.sleep(0.3)
        await gateway.stop()
    return report, seen, gateway


def main(look, cls=gateway_v9.Gateway, patience=2.0, debug=None, item_after="kettle-1l", **extra):
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))  # start the worker processes before the loop runs
        return asyncio.run(
            run(ports, sdk_pool, cpu_pool, look, cls, patience, item_after, **extra), debug=debug
        )

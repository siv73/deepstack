"""Two shutdowns of gateway v9 with steps in the wrong order.

1. The audit queue is closed before the requests in flight are drained.
2. seller-e's feed thread is left running after asyncio.run has closed the loop.
"""

import asyncio
import contextlib
import io
import logging
import threading
import warnings
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v9
from audit import AuditStore
from deploy import shopper, summary
from scoring import score_offers
from sellers_net import running_sellers
from spawn import failures

errors = Counter()


class CountErrors(logging.Handler):
    def emit(self, record):
        errors[record.getMessage().splitlines()[0].split(":")[0]] += 1


for name in ("asyncio", "gateway.background"):
    logging.getLogger(name).addHandler(CountErrors())
    logging.getLogger(name).propagate = False


async def audit_closed_first(ports, sdk_pool, cpu_pool):
    store = AuditStore()
    gateway = gateway_v9.build(ports, sdk_pool, cpu_pool, store)
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    t0 = asyncio.get_running_loop().time()
    crowd = asyncio.gather(*[shopper(port, f"sale-{n} kettle-1l", t0) for n in range(1, 11)])
    await asyncio.sleep(0.1)
    await gateway.stop()  # wrong: the audit queue closes while 10 requests still need it
    report = await gateway.shutdown([server], gateway_v9.Budget())
    results = await crowd
    return [
        summary("shoppers", results),
        *[f"  shutdown: {line}" for line in report],
        f"audit rows written: {len(store.rows)}; background failures: {dict(failures)}",
        f"errors logged: {dict(errors)}",
    ]


async def feed_left_running(ports, sdk_pool, cpu_pool, feed):
    gateway = gateway_v9.build(ports, sdk_pool, cpu_pool, AuditStore())
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    feed.subscribe(gateway.on_price_change)  # but gateway.feed is never set: shutdown forgets it
    await asyncio.sleep(0.25)
    report = await gateway.shutdown([server], gateway_v9.Budget())
    return [f"  shutdown: {line}" for line in report]


def main():
    seen = []
    threading.excepthook = lambda args: seen.append(f"{type(args.exc_value).__name__}: {args.exc_value}")
    warnings.showwarning = lambda message, category, *rest, **kw: seen.append(
        f"{category.__name__}: {message}"
    )
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))
        with contextlib.redirect_stdout(io.StringIO()):
            first = asyncio.run(audit_closed_first(ports, sdk_pool, cpu_pool))
            feed = gateway_v9.StoppableFeed([(0.2, "toaster-2s", 1059)] * 3)
            second = asyncio.run(feed_left_running(ports, sdk_pool, cpu_pool, feed))
            feed.thread.join(2)
    print("-- 1. audit queue closed before the drain --")
    print("\n".join(first))
    print("-- 2. feed thread still running when asyncio.run closed the loop --")
    print("\n".join(second))
    print(f"  feed callbacks that returned: {feed.acks}")
    print(f"  feed thread ended with: {seen}")


if __name__ == "__main__":
    main()

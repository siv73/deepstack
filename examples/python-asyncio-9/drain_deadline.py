"""Gateway v9's drain deadline: what happens to requests still running when it passes.

The audit store is slow today (200 ms a write, 2 writers), so each answer waits for its row.
10 shoppers arrive together; shutdown starts at 100 ms with a 500 ms drain budget.
"""

import asyncio
import contextlib
import io
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v9
from audit import AuditStore
from deploy import shopper, summary
from scoring import score_offers
from sellers_net import running_sellers


async def serve(ports, sdk_pool, cpu_pool):
    store = AuditStore(ms=200)
    gateway = gateway_v9.build(ports, sdk_pool, cpu_pool, store)
    gateway.audit_queue.writers = 2
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    crowd = asyncio.gather(*[shopper(port, f"sale-{n} kettle-1l", t0) for n in range(1, 11)])
    await asyncio.sleep(0.1)
    budget = gateway_v9.Budget(drain=0.5, cancel=0.2, fills=1.0, feed=0.5, flush=1.5)
    report = await gateway.shutdown([server], budget)
    results = await crowd
    print(summary("shoppers", results))
    for line in report:
        print(f"  shutdown: {line}")
    rows = Counter(row.split(": ")[1].split(" after")[0] for row in store.rows)
    print(f"audit rows written: {dict(rows)}; lost: {len(store.lost)}")


def main():
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))
        with contextlib.redirect_stdout(io.StringIO()) as hidden:
            asyncio.run(serve(ports, sdk_pool, cpu_pool))
        print("\n".join(line for line in hidden.getvalue().splitlines() if not line[:6].strip().isdigit()))


if __name__ == "__main__":
    main()

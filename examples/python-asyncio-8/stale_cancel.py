"""A stale cancel request: the count left by a refused cancel, met later by a TaskGroup."""

import asyncio
import contextlib
import io

from audit import AuditStore
from gateway_v4 import Gateway
from refuse_cancel import LOOKUPS, SlowCache
from sellers_net import running_sellers


async def handler(gateway, store, lookup):
    await lookup(SlowCache(), "kettle-1l")  # 20 ms on the cache, then the sellers
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            answer = await gateway.compare("kettle-1l")
        reply = f"200 {answer.best.seller} {answer.best.price}"
    except* ValueError:  # seller-c sent a price that is not a number: a bug, so the group failed
        reply = "502 bad price data from a seller"
    await store.write(reply)  # the audit row: the next await after the group
    return reply


async def main():
    with running_sellers(garbled={"seller-c"}) as ports:
        for name, lookup in LOOKUPS.items():
            store = AuditStore()
            task = asyncio.create_task(handler(Gateway(ports), store, lookup))
            await asyncio.wait([task])
            got = "nothing (CancelledError)" if task.cancelled() else task.result()
            print(f"{name:<32} the shopper gets: {got}; audit rows: {len(store.rows)}")


asyncio.run(main())

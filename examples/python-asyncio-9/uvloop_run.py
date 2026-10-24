"""Rung 3: gateway v10 on asyncio's own loop and on uvloop, with the same code and the same shoppers."""

import asyncio
import contextlib
import io
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v10
import incident
import uvloop
from audit import AuditStore
from scoring import score_offers
from sellers_net import running_sellers


async def serve(ports, sdk_pool, cpu_pool):
    loop = asyncio.get_running_loop()
    gateway = incident.make(gateway_v10.Gateway, ports, sdk_pool, cpu_pool, AuditStore())
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    with contextlib.redirect_stdout(io.StringIO()):
        async with server:
            replies = await asyncio.gather(
                *(incident.shopper(port, f"shop-{n}", "kettle-1l", 2) for n in range(1, 21))
            )
            await asyncio.sleep(1.0)  # seller-e's fill lands; then 20 more shoppers
            later = await asyncio.gather(
                *(incident.shopper(port, f"later-{n}", "kettle-1l", 2) for n in range(1, 21))
            )
        await gateway.shutdown([server], gateway_v10.gateway_v9.Budget())
    return [
        f"loop: {type(loop).__module__}.{type(loop).__name__}; "
        f"a SelectorEventLoop: {isinstance(loop, asyncio.SelectorEventLoop)}",
        f"  20 shoppers: {dict(Counter(replies))}; 20 more, 1 s later: {dict(Counter(later))}",
        f"  seller calls: {dict(sorted(gateway.seller_outcomes.items()))}",
    ]


def main():
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))  # start the worker processes before the loop runs
        for factory in (asyncio.EventLoop, uvloop.new_event_loop):
            print("\n".join(asyncio.run(serve(ports, sdk_pool, cpu_pool), loop_factory=factory)))


if __name__ == "__main__":
    main()

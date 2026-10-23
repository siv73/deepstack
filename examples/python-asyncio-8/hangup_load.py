"""A burst of shoppers who hang up at 50 ms: the work each gateway does for nobody."""

import asyncio
import contextlib
import io
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v6
from audit import AuditStore
from hangup_cost import Deaf
from metrics import MetricsClient, MetricsSink
from scoring import score_offers
from sellers_net import running_sellers

SHOPPERS = 10


async def burst(gateway_class, ports, sdk_pool, cpu_pool):
    gateway = gateway_class(ports, sdk_pool, cpu_pool, MetricsClient(MetricsSink()), audit=AuditStore())
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        with contextlib.redirect_stdout(io.StringIO()):
            async with asyncio.TaskGroup() as tg:
                for n in range(SHOPPERS):
                    tg.create_task(gateway_v6.shopper(port, f"shopper-{n}", "kettle-1l", hang_up_after=0.05))
            await asyncio.sleep(0.01)
            waiting = gateway.waiting  # at 60 ms: every shopper left 10 ms ago
            await asyncio.sleep(0.24)
            threads = gateway.sdk.running  # at 300 ms
            await asyncio.sleep(0.8)  # let every leftover finish before the next run
    print(f"  at 60 ms, seller calls still in progress: {waiting}")
    print(f"  at 300 ms, seller-e SDK threads still busy: {threads}")


async def main(ports, sdk_pool, cpu_pool):
    print(f"-- {SHOPPERS} shoppers hang up at 50 ms: gateway v5 behind a plain server --")
    await burst(Deaf, ports, sdk_pool, cpu_pool)
    print(f"-- the same {SHOPPERS} shoppers: gateway v6 --")
    await burst(gateway_v6.Gateway, ports, sdk_pool, cpu_pool)


if __name__ == "__main__":
    with (
        ThreadPoolExecutor(max_workers=4) as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))
        asyncio.run(main(ports, sdk_pool, cpu_pool))

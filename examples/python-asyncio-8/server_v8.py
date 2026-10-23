"""Gateway v8 as a long-running server, the way it was deployed before this page: no signal handler.

It prints "ready <port>" and serves until the process is stopped. SIGTERM then does what it
does to any Python process that has not handled it: the process ends at once.
"""

import asyncio
import contextlib
import io
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v8
from audit import AuditStore
from gateway_v9 import build, say
from scoring import score_offers
from sellers_net import running_sellers


async def run(ports, sdk_pool, cpu_pool):
    gateway = build(ports, sdk_pool, cpu_pool, AuditStore(), cls=gateway_v8.Gateway)  # v9's settings
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    say(f"ready {server.sockets[0].getsockname()[1]}")
    await asyncio.Event().wait()  # serve until the process is stopped


def main():
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
        contextlib.redirect_stdout(io.StringIO()),
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))
        asyncio.run(run(ports, sdk_pool, cpu_pool))


if __name__ == "__main__":
    sys.exit(main())

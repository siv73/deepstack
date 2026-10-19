"""Gateway v5 behind a plain server: the shopper hangs up at 100 ms and the gateway carries on."""

import asyncio
import contextlib
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v5
import gateway_v6
from audit import AuditStore
from gateway_v3 import ms_since
from metrics import MetricsClient, MetricsSink
from scoring import score_offers
from sellers_net import running_sellers


class Deaf(gateway_v6.Gateway):
    """Gateway v5's behaviour: nobody watches the connection, and seller-e's SDK keeps its 5 s timeout."""

    async def _call_by(self, deadline, start, name, port, item):
        return await gateway_v5.Gateway._call(self, start, name, port, item)

    async def serve(self, reader, writer):
        start = asyncio.get_running_loop().time()
        shopper, item = (await reader.readline()).decode().split()
        answer = await self.handle(shopper, item, start)
        said = gateway_v6.describe(answer)
        print(f"{ms_since(start):5} ms  answer ready: {said}; written to a closed connection")
        writer.write(f"{answer.best.seller} {answer.best.price}\n".encode())
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


async def run(ports, sdk_pool, cpu_pool):
    gateway = Deaf(ports, sdk_pool, cpu_pool, MetricsClient(MetricsSink()), audit=AuditStore())
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    start = asyncio.get_running_loop().time()
    async with server:
        print("-- gateway v5 behind a plain server: the shopper hangs up at 100 ms --")
        await gateway_v6.shopper(port, "shopper-2", "kettle-1l", hang_up_after=0.1)
        print("  100 ms  shopper-2 hung up")
        await asyncio.sleep(1.0)
    ended = round((gateway.sdk.last_finished - start) * 100) * 10
    print(f"        seller-e's SDK thread ended at {ended} ms")


def main():
    with (
        ThreadPoolExecutor(max_workers=4) as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))
        asyncio.run(run(ports, sdk_pool, cpu_pool))


if __name__ == "__main__":
    main()

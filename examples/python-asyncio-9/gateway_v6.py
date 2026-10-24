"""Gateway v6: gateway v5 that stops working when the shopper hangs up.

New on this page: the gateway is reached over TCP; a watcher Task notices when the shopper
closes the connection, and the request's TaskGroup then cancels everything the request
started. The deadline is passed down to seller-e's sync SDK, so its thread gives up too.
Every request leaves one audit row, written by an owned Task behind asyncio.shield().
"""

import asyncio
import contextlib
import functools
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import gateway_v5
from audit import AuditStore
from gateway_v3 import ask_seller, ms_since
from metrics import MetricsClient, MetricsSink
from scoring import score_offers
from sellers import SellerError
from sellers_net import running_sellers
from spawn import failures, spawn


class ClientGone(Exception):
    """The shopper closed the connection before the answer was ready."""


async def watch_for_hang_up(reader):
    await reader.read(1)  # a shopper sends nothing after its request, so this returns only at hang-up
    raise ClientGone


def describe(answer):
    if answer.best is None:
        return f"no offer after {answer.ms} ms"
    return f"{answer.best.seller} at {answer.best.price:,} after {answer.ms} ms"


class Gateway(gateway_v5.Gateway):
    def __init__(self, *args, audit, **kwargs):
        super().__init__(*args, **kwargs)
        self.audit = audit
        self.waiting = 0  # seller calls in progress, for the hang-up report
        self.hung_up = 0  # requests abandoned by their shopper: a metric

    async def _ask(self, start, deadline, name, port, item):
        self.waiting += 1
        try:
            async with asyncio.timeout_at(deadline):
                async with self.limit:
                    return await self._call_by(deadline, start, name, port, item)
        except TimeoutError:
            return TimeoutError(name)
        except (SellerError, OSError) as exc:
            return exc
        finally:
            self.waiting -= 1

    async def _call_by(self, deadline, start, name, port, item):
        if name == "seller-e":  # pass the deadline down: the SDK thread stops waiting then too
            loop = asyncio.get_running_loop()
            left = max(deadline - loop.time(), 0.001)
            call = functools.partial(self.sdk.get_price, item, timeout=left)
            return await loop.run_in_executor(self.sdk_pool, call)
        return await ask_seller(start, name, port, item)

    async def handle(self, shopper, item, start):
        try:
            answer = await self.compare(item)
        except asyncio.CancelledError:
            self.hung_up += 1
            await self._audit(f"{shopper} {item}: hung up after {ms_since(start)} ms")
            raise  # the cancellation travels on
        await self._audit(f"{shopper} {item}: {describe(answer)}")
        return answer

    async def _audit(self, row):
        task = spawn(self.audit.write(row), name="audit")  # owned: a strong reference, failures logged
        await asyncio.shield(task)  # if this handler is cancelled now, the write still finishes

    async def serve(self, reader, writer):
        start = asyncio.get_running_loop().time()
        shopper, item = (await reader.readline()).decode().split()
        try:
            async with asyncio.TaskGroup() as tg:
                watcher = tg.create_task(watch_for_hang_up(reader))
                answer = await self.handle(shopper, item, start)
                watcher.cancel()  # answered: stop watching
            best = answer.best
            writer.write(f"{best.seller} {best.price}\n".encode() if best else b"none\n")
            await writer.drain()
        except* ClientGone:  # the group cancelled handle(); nobody is left to answer
            print(
                f"{ms_since(start):5} ms  {shopper}'s request ended: audit row written, "
                f"{self.waiting} seller calls still waiting"
            )
        finally:
            writer.close()
            with contextlib.suppress(OSError):  # the shopper may have reset the connection
                await writer.wait_closed()


async def shopper(port, name, item, hang_up_after=None):
    """One shopper: send a request, then read the answer or hang up after `hang_up_after` seconds."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"{name} {item}\n".encode())
    await writer.drain()
    try:
        if hang_up_after is not None:
            await asyncio.sleep(hang_up_after)
            return None
        line = (await reader.readline()).decode().strip()
        return f'{name} got "{line}" after {ms_since(start)} ms'
    finally:
        writer.close()
        await writer.wait_closed()


async def serve(ports, sdk_pool, cpu_pool):
    audit = AuditStore()
    gateway = Gateway(ports, sdk_pool, cpu_pool, MetricsClient(MetricsSink()), audit=audit)
    await gateway.start()
    server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    loop = asyncio.get_running_loop()
    async with server:
        print("-- shopper-1 waits for the answer --")
        print(await shopper(port, "shopper-1", "kettle-1l"))
        await asyncio.sleep(0.7)  # let seller-e's last call end before the next case
        print("-- shopper-2 hangs up at 100 ms --")
        start = loop.time()
        await shopper(port, "shopper-2", "kettle-1l", hang_up_after=0.1)
        await asyncio.sleep(0.4)
        ended = round((gateway.sdk.last_finished - start) * 100) * 10
        print(f"        seller-e's SDK thread ended at {ended} ms: its own timeout, set from the deadline")
    await gateway.stop()
    print("audit rows:", audit.rows)
    print("hang-ups counted:", gateway.hung_up, "| background failures:", dict(failures) or "none")


def main():
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))  # start the worker processes before the loop runs
        asyncio.run(serve(ports, sdk_pool, cpu_pool))


if __name__ == "__main__":
    main()

"""Gateway v5: gateway v4 with the fixes for Part 4's six traps.

seller-e has only a sync SDK, so its calls run in a small thread pool of their own. The
CPU-bound ranking runs in a process pool. Outcomes per seller go to a metrics service from
a background Task that is owned and watched.
"""

import asyncio
import contextlib
import io
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass

import gateway_v4
from gateway_v3 import ask_seller, ms_since
from metrics import MetricsClient, MetricsSink, outcome
from scoring import score_offers
from sellers import BUDGET_MS, SellerError
from sellers_net import running_sellers
from spawn import failures, spawn
from sync_sdk import SyncSellerClient


@dataclass
class Answer(gateway_v4.Answer):
    partial: bool = False  # trap 6: say so when a seller is missing


class Gateway(gateway_v4.Gateway):
    def __init__(self, ports, sdk_pool, cpu_pool, metrics, max_in_flight=100, rounds=2000):
        super().__init__(ports, max_in_flight)
        self.sdk = SyncSellerClient(ports["seller-e"])  # seller-e has only a sync SDK
        self.sdk_pool, self.cpu_pool = sdk_pool, cpu_pool  # trap 2: its own threads; CPU in processes
        self.metrics, self.rounds = metrics, rounds
        self.flusher = None

    async def start(self):
        self.flusher = spawn(self._flush_every(1.0), name="metrics-flush")  # trap 3: owned, watched

    async def stop(self):
        self.flusher.cancel()
        await asyncio.wait([self.flusher])
        await self.metrics.flush()

    async def _flush_every(self, seconds):
        while True:
            await asyncio.sleep(seconds)
            await self.metrics.flush()

    async def _call(self, start, name, port, item):
        if name == "seller-e":  # trap 2a: the sync call runs in seller-e's own pool
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.sdk_pool, self.sdk.get_price, item)
        return await ask_seller(start, name, port, item)

    async def _ask(self, start, deadline, name, port, item):
        try:
            async with asyncio.timeout_at(deadline):
                async with self.limit:
                    return await self._call(start, name, port, item)
        except TimeoutError:  # trap 6: first, because TimeoutError is an OSError
            return TimeoutError(name)
        except (SellerError, OSError) as exc:  # trap 5: expected failures only; CancelledError passes
            return exc

    async def compare(self, item, budget_ms=BUDGET_MS):
        loop = asyncio.get_running_loop()
        start = loop.time()
        deadline = start + budget_ms / 1000
        async with asyncio.TaskGroup() as tg:  # trap 4: a TaskGroup, not gather
            tasks = {n: tg.create_task(self._ask(start, deadline, n, p, item)) for n, p in self.ports.items()}
        results = {n: t.result() for n, t in tasks.items()}
        offers = [r for r in results.values() if not isinstance(r, BaseException)]
        ranked = await loop.run_in_executor(self.cpu_pool, score_offers, offers, self.rounds)  # trap 2b
        timed_out = [n for n, r in results.items() if isinstance(r, TimeoutError)]
        failed = [(n, r) for n, r in results.items() if isinstance(r, BaseException) and n not in timed_out]
        best = ranked[0] if ranked else None
        answer = Answer(best, failed, timed_out, ms_since(start), partial=bool(timed_out or failed))
        for name in self.ports:
            await self.metrics.record(name, outcome(answer, name))  # trap 1: awaited
        return answer


def report(a):
    gateway_v4.report(a)
    if a.partial:
        print("        partial answer: the response says which sellers are missing")


async def serve(ports, sdk_pool, cpu_pool):
    sink = MetricsSink()
    gateway = Gateway(ports, sdk_pool, cpu_pool, MetricsClient(sink))
    await gateway.start()
    print("-- gateway v5: one request --")
    report(await gateway.compare("kettle-1l"))
    print("-- 10 requests at once --")
    with contextlib.redirect_stdout(io.StringIO()):
        async with asyncio.TaskGroup() as tg:
            calls = [tg.create_task(gateway.compare("kettle-1l")) for _ in range(10)]
    answers = [c.result() for c in calls]
    best = {f"{a.best.seller} at {a.best.price:,}" for a in answers}
    partial = sum(a.partial for a in answers)
    slowest = max(a.ms for a in answers)
    print(f"10 answers, all {', '.join(best)}; slowest {slowest} ms; partial: {partial} of 10")
    sdk = gateway.sdk
    print(f"seller-e's SDK: 11 calls asked for, {sdk.started} started, at most {sdk.peak} at once")
    await gateway.stop()
    print("metrics service received:", sink.totals())
    print("background failures:", dict(failures) or "none")


def main():
    # The pools are made, started and closed outside the event loop: starting worker processes
    # and closing a pool both make the caller wait, which inside a coroutine would block the loop.
    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[], []], [1, 1]))  # start the worker processes before the loop runs
        asyncio.run(serve(ports, sdk_pool, cpu_pool))


if __name__ == "__main__":
    main()

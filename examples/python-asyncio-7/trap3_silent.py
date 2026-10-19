"""Trap 3b: a background Task that fails, and who finds out. The metrics service is down."""

import asyncio
import gc
import logging

import spawn
from metrics import MetricsClient, MetricsSink


async def flush_every(metrics, seconds):
    """The gateway's background job: send the piled-up counts every few seconds."""
    while True:
        await asyncio.sleep(seconds)
        await metrics.flush()


class Gateway:
    def __init__(self, metrics):
        self.metrics = metrics

    def start_kept(self):
        self.flusher = asyncio.create_task(flush_every(self.metrics, 0.05))  # kept, never read

    def start_bare(self):
        asyncio.create_task(flush_every(self.metrics, 0.05))  # no reference, never read

    def start_spawned(self):
        self.flusher = spawn.spawn(flush_every(self.metrics, 0.05), name="metrics-flush")


async def run(how):
    heard = []  # every place a failure could be reported: asyncio's handler and our logs
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(lambda _loop, ctx: heard.append(f"asyncio: {ctx['message']}"))
    listener = ListHandler(heard)
    logging.getLogger("gateway").addHandler(listener)
    metrics = MetricsClient(MetricsSink(down=True))
    await metrics.record("seller-e", "timed out")
    gateway = Gateway(metrics)
    getattr(gateway, f"start_{how}")()
    await asyncio.sleep(0.2)  # the first flush fails at about 55 ms
    gc.collect()
    logging.getLogger("gateway").removeHandler(listener)
    flusher = getattr(gateway, "flusher", None)
    state = "no reference left" if flusher is None else f"done={flusher.done()}"
    print(f"flusher Task: {state}; failure reported: {'; '.join(heard) or 'nowhere'}")


async def main():
    print("-- create_task(), kept in self.flusher, never awaited --")
    await run("kept")
    print("-- create_task(), no reference kept --")
    await run("bare")
    print("-- spawn(): a strong reference plus a done callback that reads the exception --")
    await run("spawned")
    print("background failures counted:", dict(spawn.failures))


class ListHandler(logging.Handler):
    def __init__(self, heard):
        super().__init__()
        self.heard = heard

    def emit(self, record):
        self.heard.append(f"{record.name}: {record.getMessage()}")


if __name__ == "__main__":
    asyncio.run(main())

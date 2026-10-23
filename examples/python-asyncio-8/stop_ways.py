"""Hard stop, drain, or durable handoff: 8 jobs, a stop at 350 ms, and a replacement worker after it.

Each job charges an order (at 100 ms) and records the result (at 200 ms). Two jobs run at once.
A job taken from a durable broker is acknowledged only when it is done; one taken from an
in-process queue is gone from the queue as soon as it is taken. The replacement worker then
processes whatever the first one left, so we can count lost and doubled charges.
"""

import asyncio
from collections import Counter


class Broker:
    """Durable: survives the worker. A job taken but not acknowledged is delivered again."""

    def __init__(self, jobs):
        self.ready, self.taken = list(jobs), set()

    def take(self):
        job = self.ready.pop(0) if self.ready else None
        if job is not None:
            self.taken.add(job)
        return job

    def ack(self, job):
        self.taken.discard(job)

    def redeliver(self):  # what the broker does when the worker's connection drops
        self.ready = sorted(self.taken) + self.ready
        self.taken.clear()


class Memory:
    """In-process: dies with the worker. Taking a job removes it."""

    def __init__(self, jobs):
        self.ready = list(jobs)

    def take(self):
        return self.ready.pop(0) if self.ready else None

    def ack(self, job):
        pass

    def redeliver(self):
        pass


async def worker(source, charges, recorded, idempotent, stop):
    while not stop.is_set() and (job := source.take()) is not None:
        await asyncio.sleep(0.1)
        if not (idempotent and job in charges):  # an idempotency key: charge each order once
            charges[job] += 1
        await asyncio.sleep(0.1)
        recorded.add(job)
        source.ack(job)


async def run(way, durable, idempotent):
    jobs = range(1, 9)
    source = Broker(jobs) if durable else Memory(jobs)
    charges, recorded, stop = Counter(), set(), asyncio.Event()
    workers = [asyncio.create_task(worker(source, charges, recorded, idempotent, stop)) for _ in range(2)]
    await asyncio.sleep(0.35)
    stop.set()  # SIGTERM: take no new jobs
    if way == "hard stop":
        for task in workers:
            task.cancel()  # SIGKILL: the jobs in progress stop where they are, nothing acknowledged
        await asyncio.wait(workers)
    else:
        try:  # drain: finish the jobs in progress within 0.3 s
            async with asyncio.timeout(0.3):
                await asyncio.gather(*workers)
        except TimeoutError:
            pass
    source.redeliver()
    if durable:  # the replacement worker, after the deploy
        await asyncio.gather(
            *(worker(source, charges, recorded, idempotent, asyncio.Event()) for _ in range(2))
        )
    lost = [j for j in jobs if charges[j] == 0]
    doubled = [j for j in jobs if charges[j] > 1]
    half = [j for j in jobs if charges[j] and j not in recorded]
    store = "broker" if durable else "memory"
    head = f"{way:9} {store:6} idempotent={idempotent!s:5}"
    return f"{head}: never charged {lost}, charged twice {doubled}, charged but not recorded {half}"


async def main():
    for way, durable, idempotent in (
        ("hard stop", False, False),
        ("drain", False, False),
        ("hard stop", True, False),
        ("drain", True, False),
        ("hard stop", True, True),
    ):
        print(await run(way, durable, idempotent))


asyncio.run(main())

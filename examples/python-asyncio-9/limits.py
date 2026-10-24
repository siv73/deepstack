"""Per-seller limits: a cap on calls in flight, a short line for that cap, and an optional rate."""

import asyncio
from collections import Counter


class Skipped(Exception):
    """A seller call that was not made, because a limit said no."""


class SellerLimits:
    def __init__(self, caps, max_waiting, rates):
        self.caps = {name: asyncio.Semaphore(n) for name, n in caps.items()}
        self.max_waiting, self.rates = max_waiting, rates
        self.waiting = Counter()  # calls waiting for each seller's cap right now
        self.skipped = Counter()  # one metric per seller and reason

    async def call(self, name, make_call):
        """Run make_call() under `name`'s limits, or raise Skipped at once. The caller sets the deadline."""
        cap = self.caps[name]
        if cap.locked() and self.waiting[name] >= self.max_waiting[name]:
            self.skipped[f"{name}: line full"] += 1
            raise Skipped(f"{name} line full")
        bucket = self.rates.get(name)
        if bucket is not None and not bucket.try_take():
            self.skipped[f"{name}: over its rate"] += 1
            raise Skipped(f"{name} over its rate")
        self.waiting[name] += 1
        try:
            await cap.acquire()  # waits in line; the caller's deadline can cut this wait
        finally:
            self.waiting[name] -= 1
        try:
            return await make_call()
        finally:
            cap.release()

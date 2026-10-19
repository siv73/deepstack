"""Seller calls per second for one seller at 10 times the load, from a cache with a fixed or jittered TTL.

A model, not a run: every item is asked for at least once a second in every process, so each
cache entry is refilled the moment it expires, by one single-flight call per process.
"""

import random
from collections import Counter

PROCESSES = 10  # gateway processes behind the load balancer
ITEMS = 5_000  # distinct items in the sale, all hot
TTL = 30.0  # seconds a price is kept
HORIZON = 120  # seconds simulated after a deploy that started every process with an empty cache


def calls_per_second(caches, jitter, seed=7):
    """caches: how many independent caches (one per process, or one shared). jitter: +/- fraction."""
    rng = random.Random(seed)
    per_second = Counter()
    for _ in range(caches):
        for _ in range(ITEMS):
            t = 0.0  # every entry is filled in the first second after the deploy
            while t < HORIZON:
                per_second[int(t)] += 1
                t += TTL * (1 + rng.uniform(-jitter, jitter))
    return per_second


def describe(label, caches, jitter):
    per_second = calls_per_second(caches, jitter)
    later = {s: n for s, n in per_second.items() if s >= 1}  # second 0 is the deploy itself
    peak_second, peak = max(later.items(), key=lambda kv: (kv[1], -kv[0]))
    long_run = caches * ITEMS / TTL  # each cache refills each item once per TTL
    worst = f"worst second after the deploy: {peak:6,} (at {peak_second} s)"
    print(f"  {label:32} long-run {long_run:5,.0f} calls/s; {worst}")


if __name__ == "__main__":
    print(f"{PROCESSES} processes, {ITEMS:,} hot items, TTL {TTL:.0f} s; calls to one seller")
    describe("cache per process, fixed TTL", PROCESSES, 0.0)
    describe("cache per process, TTL +/- 10%", PROCESSES, 0.10)
    describe("one shared cache, TTL +/- 10%", 1, 0.10)

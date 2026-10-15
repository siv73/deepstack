"""CPU-bound work in the gateway: a pure-Python ranking step over the offers.

It computes, waits for nothing, and never awaits. It lives in its own module so a process
pool's worker processes can import it by name.
"""

import time


def score_offers(offers, rounds):
    """Rank the offers, cheapest first. `rounds` sets how much CPU each offer costs."""
    ranked = []
    for offer in offers:
        risk = 0
        for i in range(rounds):  # stands in for a pure-Python model
            risk = (risk * 31 + offer.price + i) % 1_000_003
        ranked.append((offer.price, risk, offer))
    ranked.sort(key=lambda row: (row[0], row[1]))
    return [offer for _, _, offer in ranked]


def rounds_for(ms, offers=4):
    """How many rounds make one score_offers() call take about `ms` of CPU on this machine."""
    from sellers import Offer

    sample = [Offer("calibrate", 1000 + i) for i in range(offers)]
    took = []
    for _ in range(3):  # the fastest of three runs: least disturbed by other work
        start = time.process_time()
        score_offers(sample, 200_000)
        took.append(time.process_time() - start)
    return max(1, round(200_000 * (ms / 1000) / min(took)))

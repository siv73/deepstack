"""Gateway v0: ask the five sellers one after another, on one thread."""

import time

from sellers import SELLERS, Offer, cheapest


def ask_seller_blocking(seller, item):
    time.sleep(seller.latency_ms / 1000)  # stands in for the network call
    return Offer(seller.name, seller.price)


def compare(item):
    start = time.perf_counter()
    offers = []
    for seller in SELLERS:
        offers.append(ask_seller_blocking(seller, item))
        elapsed = (time.perf_counter() - start) * 1000 // 10 * 10  # rounded down to 10 ms
        print(f"{elapsed:5.0f} ms  {seller.name} answered {seller.price:,}")
    best = cheapest(offers)
    total = (time.perf_counter() - start) * 1000 // 10 * 10
    print(f"cheapest: {best.seller} at {best.price:,} after {total:,.0f} ms")
    return best, total


if __name__ == "__main__":
    compare("kettle-1l")

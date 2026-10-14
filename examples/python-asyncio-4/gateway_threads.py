"""The thread answer: one thread per seller call, so the five waits overlap."""

import threading
import time

from gateway_v0 import ask_seller_blocking
from sellers import SELLERS, cheapest


def compare(item):
    start = time.perf_counter()
    offers = []

    def worker(seller):
        offers.append(ask_seller_blocking(seller, item))  # list.append is safe across threads

    threads = [threading.Thread(target=worker, args=(s,)) for s in SELLERS]
    for t in threads:
        t.start()
    print(f"threads waiting: {threading.active_count() - 1}")  # minus the main thread
    for t in threads:
        t.join()
    best = cheapest(offers)
    total = (time.perf_counter() - start) * 1000 // 10 * 10  # rounded down to 10 ms
    print(f"cheapest: {best.seller} at {best.price:,} after {total:,.0f} ms")
    return best, total


if __name__ == "__main__":
    compare("kettle-1l")

"""A forgotten await: seller-c "answers" at 0 ms without ever waiting for the seller."""

import gc
import warnings

from gateway_v1 import ask_seller, compare, report
from sellers import BUDGET_MS, Offer
from toyloop import sleep


async def ask_seller_forgot_await(loop, seller, item, faulty=()):
    if seller.name != "seller-c":
        return await ask_seller(loop, seller, item, faulty)
    sleep(seller.latency_ms)  # BUG: no await, so this only builds a coroutine and drops it
    print(f"{loop.now:5} ms  {seller.name} answered {seller.price:,}")
    return Offer(seller.name, seller.price)


with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    report(*compare("kettle-1l", budget_ms=BUDGET_MS, ask=ask_seller_forgot_await))
    gc.collect()
for warning in caught:
    print(f"{warning.category.__name__}: {warning.message}")

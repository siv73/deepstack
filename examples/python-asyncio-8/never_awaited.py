"""A coroutine that is created but never awaited does nothing, and Python warns."""

import gc
import warnings


async def save_receipt(order_id):
    print("saved receipt", order_id)


with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    save_receipt(42)  # missing await: the body never runs
    gc.collect()  # make sure the dropped coroutine is cleaned up now

print("receipts saved: 0")
for warning in caught:
    print(f"{warning.category.__name__}: {warning.message}")

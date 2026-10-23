"""One seller handler makes a blocking call: every other seller waits behind it."""

import time

from gateway_v1 import ask_seller, compare, report
from sellers import BUDGET_MS


async def ask_seller_with_blocking_call(loop, seller, item, faulty=()):
    if seller.name == "seller-b":
        time.sleep(0.3)  # a blocking call (say, a sync SDK) holds the only thread for 300 ms
    return await ask_seller(loop, seller, item, faulty)


if __name__ == "__main__":
    print("-- no budget --")
    report(*compare("kettle-1l", ask=ask_seller_with_blocking_call))
    print(f"-- {BUDGET_MS} ms budget --")
    report(*compare("kettle-1l", budget_ms=BUDGET_MS, ask=ask_seller_with_blocking_call))

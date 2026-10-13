"""Part 1's fault, on asyncio: seller-c fails, and the failure stays inside its own Task."""

import asyncio

from gateway_v3 import compare, report
from sellers import BUDGET_MS
from sellers_net import running_sellers


async def main():
    with running_sellers(faulty={"seller-c"}) as ports:
        best, failed, missed, ms = await compare(ports, "kettle-1l", budget_ms=BUDGET_MS)
    report(best, failed, missed, ms)


asyncio.run(main())

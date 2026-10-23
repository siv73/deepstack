"""Seven small traps for a linter. test_lint4.py runs ruff's asyncio rules over this file."""

import asyncio
import logging
import time
import urllib.request

from sync_sdk import SyncSellerClient

log = logging.getLogger(__name__)


async def sleeps():
    time.sleep(0.3)  # trap 2: a blocking sleep


async def fetches(url):
    return urllib.request.urlopen(url).read()  # trap 2: a blocking HTTP call


async def calls_the_sdk(sdk: SyncSellerClient):
    return sdk.get_price("kettle-1l")  # trap 2: the same blocking, inside a library


async def fires_and_forgets(coro):
    asyncio.create_task(coro)  # trap 3: no reference kept


async def swallows(call):
    try:
        return await call()
    except BaseException:  # trap 5: swallows CancelledError, silently
        return None


async def swallows_and_logs(call):
    try:
        return await call()
    except BaseException:  # trap 5: swallows CancelledError, and logs it
        log.exception("seller call failed")
        return None


async def forgets_the_await(metrics):
    metrics.record("seller-e", "timed out")  # trap 1: no await

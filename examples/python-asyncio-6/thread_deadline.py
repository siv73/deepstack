"""What cancel() cannot reach: a running thread. Passing the deadline down is what stops it early."""

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor

from sellers_net import running_sellers
from sync_sdk import SyncSellerClient


async def ask(pool, sdk, timeout):
    loop = asyncio.get_running_loop()
    start = loop.time()
    call = functools.partial(sdk.get_price, "kettle-1l", timeout=timeout)
    future = loop.run_in_executor(pool, call)
    try:
        async with asyncio.timeout(0.25):  # the request's deadline
            await future
    except TimeoutError:
        cut = round((loop.time() - start) * 100) * 10
    while sdk.running:  # watch the thread itself, to see when it really ends
        await asyncio.sleep(0.01)
    ended = round((sdk.last_finished - start) * 100) * 10
    state = f"future cancelled={future.cancelled()}"
    print(f"the wait was cut at {cut} ms ({state}); the thread ended at {ended} ms")


async def main():
    with running_sellers() as ports, ThreadPoolExecutor(max_workers=1) as pool:
        sdk = SyncSellerClient(ports["seller-e"])
        print("-- seller-e's SDK with its own 5 s socket timeout --")
        await ask(pool, sdk, timeout=None)
        print("-- the same call with the deadline passed down as its timeout (0.25 s) --")
        await ask(pool, sdk, timeout=0.25)


asyncio.run(main())

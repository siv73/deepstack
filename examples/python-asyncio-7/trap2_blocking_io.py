"""Trap 2a: seller-e has only a sync SDK. Called from a coroutine, it freezes the loop."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from gateway_v3 import ask_seller, ms_since
from gateway_v4 import Gateway, report
from sellers import SellerError
from sellers_net import running_sellers
from sync_sdk import SyncSellerClient


class Blocking(Gateway):
    def __init__(self, ports, sdk_pool=None):
        super().__init__(ports)
        self.sdk, self.sdk_pool = SyncSellerClient(ports["seller-e"]), sdk_pool

    async def call(self, start, name, port, item):
        if name == "seller-e":
            return self.sdk.get_price(item)  # BUG: holds the loop's only thread for 900 ms
        return await ask_seller(start, name, port, item)

    async def _ask(self, start, deadline, name, port, item):  # gateway v4's _ask, calling call()
        try:
            async with asyncio.timeout_at(deadline):
                async with self.limit:
                    return await self.call(start, name, port, item)
        except TimeoutError:
            return TimeoutError(name)
        except (SellerError, OSError) as exc:
            return exc


class InAThread(Blocking):
    async def call(self, start, name, port, item):
        if name == "seller-e":  # the same sync call, in a thread of seller-e's own pool
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.sdk_pool, self.sdk.get_price, item)
        return await ask_seller(start, name, port, item)


async def main():
    with running_sellers() as ports:
        print("-- seller-e's sync SDK called from a coroutine --")
        report(await Blocking(ports).compare("kettle-1l"))
        print("-- the same call in seller-e's own thread pool (4 threads) --")
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="seller-e-sdk") as pool:
            gateway = InAThread(ports, sdk_pool=pool)
            start = asyncio.get_running_loop().time()
            report(await gateway.compare("kettle-1l"))
            print(f"seller-e calls still running in a thread after the answer: {gateway.sdk.running}")
            while gateway.sdk.running:
                await asyncio.sleep(0.01)
            print(f"{ms_since(start):5} ms  seller-e's thread finished; nobody was waiting for it")


if __name__ == "__main__":
    asyncio.run(main())

"""asyncio.timeout, timeout_at and wait_for on the slowest seller."""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers


async def main():
    with running_sellers() as ports:
        loop = asyncio.get_running_loop()

        print("-- timeout(0.25) around seller-e --")
        start = loop.time()
        try:
            async with asyncio.timeout(0.25) as cm:
                await ask_seller(start, "seller-e", ports["seller-e"], "kettle-1l")
        except TimeoutError:
            print(f"TimeoutError after {ms_since(start)} ms; expired() = {cm.expired()}")

        print("-- one deadline for two calls in a row: timeout_at(start + 0.25) --")
        start = loop.time()
        deadline = start + 0.25  # an absolute time on the loop's clock
        try:
            async with asyncio.timeout_at(deadline):
                await ask_seller(start, "seller-a", ports["seller-a"], "kettle-1l")
                await ask_seller(start, "seller-e", ports["seller-e"], "kettle-1l")
        except TimeoutError:
            print(f"TimeoutError after {ms_since(start)} ms, not 80 + 250 = 330")

        print("-- wait_for(seller-e, 0.25) --")
        start = loop.time()
        try:
            await asyncio.wait_for(ask_seller(start, "seller-e", ports["seller-e"], "kettle-1l"), 0.25)
        except TimeoutError:
            print(f"TimeoutError after {ms_since(start)} ms")

        print("-- nested: 0.1 s for seller-d inside a 0.25 s request --")
        start = loop.time()
        async with asyncio.timeout(0.25):
            try:
                async with asyncio.timeout(0.1):  # the inner, earlier deadline fires first
                    await ask_seller(start, "seller-d", ports["seller-d"], "kettle-1l")
            except TimeoutError:
                print(f"inner TimeoutError after {ms_since(start)} ms; the request goes on")
            await ask_seller(start, "seller-b", ports["seller-b"], "kettle-1l")
        print(f"request finished after {ms_since(start)} ms")


if __name__ == "__main__":
    asyncio.run(main())

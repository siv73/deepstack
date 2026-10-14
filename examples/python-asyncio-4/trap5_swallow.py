"""Trap 5: a retry wrapper that catches BaseException swallows the deadline's cancellation."""

import asyncio

from gateway_v3 import ask_seller
from gateway_v4 import Gateway, report
from sellers import SellerError
from sellers_net import running_sellers


async def retry_anything(call, attempts=2):
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except BaseException:  # BUG: "retry on anything" also catches CancelledError
            if attempt == attempts:
                raise
            await asyncio.sleep(0.05)  # back off, then try again


async def retry_errors(call, attempts=2):
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except (SellerError, ConnectionError):  # only what a retry can fix
            if attempt == attempts:
                raise
            await asyncio.sleep(0.05)


class WithRetry(Gateway):
    retry = staticmethod(retry_anything)

    async def _ask(self, start, deadline, name, port, item):
        try:
            async with asyncio.timeout_at(deadline) as cm:
                async with self.limit:
                    return await self.retry(lambda: ask_seller(start, name, port, item))
        except TimeoutError:
            return TimeoutError(name)
        except (SellerError, OSError) as exc:
            return exc
        finally:
            if name == "seller-e":
                print(f"        seller-e's timeout: expired() = {cm.expired()}")


class Fixed(WithRetry):
    retry = staticmethod(retry_errors)


async def main():
    with running_sellers() as ports:
        print("-- retry wrapper with except BaseException --")
        report(await WithRetry(ports).compare("kettle-1l"))
        print("-- retry wrapper that catches only seller and connection errors --")
        report(await Fixed(ports).compare("kettle-1l"))


if __name__ == "__main__":
    asyncio.run(main())

"""Clean-up that awaits too long: the deadline fires on time, but the answer is late."""

import asyncio
import contextlib
import io

from gateway_v3 import ask_seller
from gateway_v4 import Gateway, report
from sellers import SellerError
from sellers_net import running_sellers


async def tell_seller_we_gave_up(name):
    await asyncio.sleep(0.4)  # a "cancel my request" call to a slow seller: 400 ms


async def unbounded(name):
    await tell_seller_we_gave_up(name)  # BUG: the clean-up can wait as long as it likes


async def bounded(name):
    try:
        async with asyncio.timeout(0.02):  # the clean-up gets 20 ms, no more
            await tell_seller_we_gave_up(name)
    except TimeoutError:
        pass  # give up on the notice, never on the request


class WithCleanup(Gateway):
    def __init__(self, ports, cleanup):
        super().__init__(ports)
        self.cleanup = cleanup

    async def call(self, start, name, port, item):
        try:
            return await ask_seller(start, name, port, item)
        except asyncio.CancelledError:
            await self.cleanup(name)  # runs inside the deadline's block, after the cancel
            raise

    async def _ask(self, start, deadline, name, port, item):  # gateway v4's, calling self.call
        try:
            async with asyncio.timeout_at(deadline):
                async with self.limit:
                    return await self.call(start, name, port, item)
        except TimeoutError:
            return TimeoutError(name)
        except (SellerError, OSError) as exc:
            return exc


async def main():
    with running_sellers() as ports:
        for title, cleanup in [
            ("clean-up awaits a 400 ms call", unbounded),
            ("clean-up bounded to 20 ms", bounded),
        ]:
            print(f"-- {title} --")
            with contextlib.redirect_stdout(io.StringIO()):
                answer = await WithCleanup(ports, cleanup).compare("kettle-1l")
            report(answer)


asyncio.run(main())

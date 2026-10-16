"""Trap 2a, at load: to_thread() shares the loop's default pool with DNS lookups.

The sellers are reached by host name ("localhost"), as real sellers would be, so every
connection first needs a lookup, and the loop runs lookups in its default thread pool.
"""

import asyncio
import contextlib
import io
import socket
from concurrent.futures import ThreadPoolExecutor

from gateway_v4 import Answer, report
from sellers import Offer, SellerError
from sellers_net import running_sellers
from trap2_blocking_io import Blocking

DEFAULT_POOL = 4  # small, so the numbers are easy to follow


async def ask_by_name(name, port, item):
    reader, writer = await asyncio.open_connection("localhost", port, family=socket.AF_INET)
    try:
        writer.write(f"{item}\n".encode())
        await writer.drain()
        line = (await reader.readline()).decode().strip()
    finally:
        writer.close()
        await writer.wait_closed()
    if line == "ERROR":
        raise SellerError(f"{name} failed")
    seller, price = line.split()
    return Offer(seller, int(price))


class ToThread(Blocking):
    async def call(self, start, name, port, item):
        if name == "seller-e":
            return await asyncio.to_thread(self.sdk.get_price, item)  # the loop's default pool
        return await ask_by_name(name, port, item)


class OwnPool(Blocking):
    async def call(self, start, name, port, item):
        if name == "seller-e":
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.sdk_pool, self.sdk.get_price, item)
        return await ask_by_name(name, port, item)


async def fifth_request(gateway_class, ports, sdk_pool):
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=DEFAULT_POOL))
    gateway = gateway_class(ports, sdk_pool=sdk_pool)
    async with asyncio.TaskGroup() as tg:
        for _ in range(4):  # four requests already in flight
            tg.create_task(gateway.compare("kettle-1l"))
        await asyncio.sleep(0.1)
        fifth: Answer = await gateway.compare("kettle-1l")  # a new request, 100 ms later
    return fifth


async def main():
    with running_sellers() as ports, ThreadPoolExecutor(max_workers=4) as sdk_pool:
        print(f"-- seller-e via to_thread(): one default pool of {DEFAULT_POOL} threads for everything --")
        with contextlib.redirect_stdout(io.StringIO()):
            answer = await fifth_request(ToThread, ports, sdk_pool)
        print("request 5, sent at 100 ms:", end=" ")
        report(answer)
        print("-- seller-e in its own pool of 4; the default pool stays free for lookups --")
        with contextlib.redirect_stdout(io.StringIO()):
            answer = await fifth_request(OwnPool, ports, sdk_pool)
        print("request 5, sent at 100 ms:", end=" ")
        report(answer)


if __name__ == "__main__":
    asyncio.run(main())

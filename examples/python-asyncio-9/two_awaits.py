"""Two awaits in a row take the sum; two Tasks started first take the longer one."""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers


async def in_a_row(ports, names):
    start = asyncio.get_running_loop().time()
    for name in names:
        await ask_seller(start, name, ports[name], "kettle-1l")  # wait, then the next one
    return ms_since(start)


async def tasks_first(ports, names):
    start = asyncio.get_running_loop().time()
    tasks = [asyncio.create_task(ask_seller(start, n, ports[n], "kettle-1l")) for n in names]
    for task in tasks:
        await task  # every call is already in flight
    return ms_since(start)


async def main():
    with running_sellers() as ports:
        print("-- await seller-a, then await seller-b --")
        print(f"total: {await in_a_row(ports, ['seller-a', 'seller-b'])} ms")
        print("-- create both Tasks, then await them --")
        print(f"total: {await tasks_first(ports, ['seller-a', 'seller-b'])} ms")
        print("-- await all five in a row --")
        print(f"total: {await in_a_row(ports, list(ports)):,} ms")


if __name__ == "__main__":
    asyncio.run(main())

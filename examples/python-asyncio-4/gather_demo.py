"""gather(): run the five seller calls together and get the results in argument order."""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers


async def ask_all(ports, return_exceptions=False):
    start = asyncio.get_running_loop().time()
    names = ["seller-e", "seller-d", "seller-c", "seller-b", "seller-a"]  # slowest first
    calls = [ask_seller(start, n, ports[n], "kettle-1l") for n in names]  # coroutines
    results = await asyncio.gather(*calls, return_exceptions=return_exceptions)
    return results, ms_since(start)


def show(item):
    return (
        f"{type(item).__name__}: {item}" if isinstance(item, Exception) else f"{item.seller} {item.price:,}"
    )


async def main():
    with running_sellers() as ports:
        print("-- gather, every seller answers --")
        results, ms = await ask_all(ports)
        print(f"after {ms} ms, in argument order:", "; ".join(map(show, results)))
    with running_sellers(faulty={"seller-c"}) as ports:
        print("-- gather(return_exceptions=True), seller-c fails --")
        results, ms = await ask_all(ports, return_exceptions=True)
        print(f"after {ms} ms, in argument order:", "; ".join(map(show, results)))


if __name__ == "__main__":
    asyncio.run(main())

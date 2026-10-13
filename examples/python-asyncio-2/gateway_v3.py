"""Gateway v3: the same gateway on asyncio's real loop, with streams and Tasks."""

import asyncio

from sellers import BUDGET_MS, Offer, SellerError, cheapest
from sellers_net import running_sellers


async def ask_seller(start, name, port, item):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
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
    print(f"{ms_since(start):5} ms  {seller} answered {int(price):,}")
    return Offer(seller, int(price))


def ms_since(start):
    return round((asyncio.get_running_loop().time() - start) * 100) * 10


async def compare(ports, item, budget_ms=None):
    loop = asyncio.get_running_loop()
    start = loop.time()
    tasks = [asyncio.create_task(ask_seller(start, n, p, item), name=n) for n, p in ports.items()]
    if budget_ms is not None:  # a hand-made budget; Part 3 replaces it with a real timeout
        loop.call_later(budget_ms / 1000, lambda: [t.cancel() for t in tasks if not t.done()])
    all_done = loop.create_future()  # a hand-made "wait for all": Part 3 replaces it too
    remaining = len(tasks)

    def one_done(_task):
        nonlocal remaining
        remaining -= 1
        if remaining == 0:
            all_done.set_result(None)

    for task in tasks:
        task.add_done_callback(one_done)
    await all_done
    missed = [t.get_name() for t in tasks if t.cancelled()]
    failed = [(t.get_name(), t.exception()) for t in tasks if not t.cancelled() and t.exception()]
    offers = [t.result() for t in tasks if not t.cancelled() and not t.exception()]
    return cheapest(offers), failed, missed, ms_since(start)


def report(best, failed, missed, ms):
    line = f"cheapest: {best.seller} at {best.price:,} after {ms:,} ms"
    if failed:
        line += "; failed: " + ", ".join(f"{n} ({type(e).__name__}: {e})" for n, e in failed)
    if missed:
        line += "; missed: " + ", ".join(missed)
    print(line)


async def main():
    with running_sellers() as ports:
        print("-- wait for every seller --")
        report(*await compare(ports, "kettle-1l"))
        print(f"-- stop at the {BUDGET_MS} ms budget --")
        report(*await compare(ports, "kettle-1l", budget_ms=BUDGET_MS))


if __name__ == "__main__":
    asyncio.run(main())

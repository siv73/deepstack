"""Trap 4: gather() keeps going after it fails, and two of its failures make no sound."""

import asyncio
import gc

from gateway_v3 import ask_seller, ms_since
from sellers import BUDGET_MS, cheapest
from sellers_net import running_sellers


async def first_error_only(ports):
    """seller-c fails at 150 ms and seller-d at 200 ms. Who hears about seller-d?"""
    heard = []
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(lambda _loop, ctx: heard.append(ctx["message"]))
    start = loop.time()
    tasks = [asyncio.create_task(ask_seller(start, n, p, "kettle-1l"), name=n) for n, p in ports.items()]
    for task in tasks:  # say when each call ends, without reading its result
        task.add_done_callback(lambda t: print(f"{ms_since(start):5} ms  {t.get_name()}'s Task ended"))
    try:
        await asyncio.gather(*tasks)
    except Exception as exc:
        print(f"{ms_since(start):5} ms  gather raised {type(exc).__name__}: {exc}")
    await asyncio.wait(tasks)  # watch what the other calls do next
    del tasks, task
    gc.collect()
    print(f"after the Tasks were garbage-collected, asyncio reported: {heard or 'nothing'}")
    control = asyncio.create_task(ask_seller(start, "seller-d", ports["seller-d"], "kettle-1l"))
    await asyncio.wait([control])
    del control
    gc.collect()
    print(f"control: the same failure in a plain Task nobody reads: {heard or 'nothing'}")


async def cancelled_in_the_results(ports):
    """Part 2's hand-made budget, with gather(return_exceptions=True) collecting the results."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    tasks = [asyncio.create_task(ask_seller(start, n, p, "kettle-1l")) for n, p in ports.items()]
    loop.call_later(BUDGET_MS / 1000, lambda: [t.cancel() for t in tasks if not t.done()])
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(f"{ms_since(start):5} ms  results: {[type(r).__name__ for r in results]}")
    offers = [r for r in results if not isinstance(r, Exception)]  # BUG: CancelledError is not an Exception
    try:
        best = cheapest(offers)
        print(f"cheapest: {best.seller} at {best.price:,}")
    except AttributeError as exc:
        print(f"the request crashed: AttributeError: {exc}")
    offers = [r for r in results if not isinstance(r, BaseException)]  # the fix
    best = cheapest(offers)
    print(f"with isinstance(r, BaseException): cheapest: {best.seller} at {best.price:,}")


async def main():
    with running_sellers(faulty={"seller-c", "seller-d"}) as ports:
        print("-- gather(), default settings; seller-c and seller-d both fail --")
        await first_error_only(ports)
    with running_sellers() as ports:
        print("-- gather(return_exceptions=True), seller-e cancelled by the budget --")
        await cancelled_in_the_results(ports)


if __name__ == "__main__":
    asyncio.run(main())

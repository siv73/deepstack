"""Crossing between threads and the loop: to_thread, call_soon_threadsafe, run_coroutine_threadsafe."""

import asyncio
import contextvars
import functools
import threading
from concurrent.futures import ThreadPoolExecutor

from price_feed import PriceFeed
from request_log import request_id

cache = {}


def where():
    return f"thread {threading.current_thread().name}, request_id {request_id.get()}"


def blocking_lookup(item):  # any sync call: the SDK, a file, a C library
    return where()


async def apply_change(item, offer):  # a coroutine the feed thread needs run, and waits for
    await asyncio.sleep(0.01)  # e.g. the audit row for the change
    if offer.price <= 0:
        raise ValueError(f"bad price {offer.price}")
    cache[item] = offer.price
    return f"applied {item} {offer.price:,} ({where()})"


async def main():
    loop = asyncio.get_running_loop()
    request_id.set("shopper-1")
    print("1. a blocking call, from a coroutine")
    print(f"   to_thread:                       {await asyncio.to_thread(blocking_lookup, 'kettle-1l')}")
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="seller-e-sdk") as pool:
        plain = await loop.run_in_executor(pool, blocking_lookup, "kettle-1l")
        ctx = contextvars.copy_context()
        carried = await loop.run_in_executor(pool, functools.partial(ctx.run, blocking_lookup, "kettle-1l"))
    print(f"   run_in_executor(own pool):       {plain}")
    print(f"   run_in_executor + ctx.run:       {carried}")

    print("2. a callback, from the SDK's thread: fire and forget")
    done = asyncio.Event()

    def on_change(item, offer):  # runs in the feed's thread
        def put():  # runs on the loop's thread
            cache[item] = offer.price
            print(f"   call_soon_threadsafe ran put() in {where()}")
            done.set()

        loop.call_soon_threadsafe(put)
        return "queued"

    feed = PriceFeed([(0.0, "kettle-1l", 1099)])
    feed.subscribe(on_change)
    await done.wait()
    print(f"   cache now {cache}; the feed's callback returned {feed.acks}")

    print("3. a coroutine, from the SDK's thread: wait for its result")

    def on_change_and_wait(item, offer):  # runs in the feed's thread
        future = asyncio.run_coroutine_threadsafe(apply_change(item, offer), loop)
        try:
            return future.result(timeout=1.0)  # this thread waits; the loop does not
        except ValueError as e:
            return f"failed: {e}"

    feed = PriceFeed([(0.0, "kettle-1l", 1079), (0.05, "toaster-2s", -5)])
    feed.subscribe(on_change_and_wait)
    await asyncio.to_thread(feed.join)
    for ack in feed.acks:
        print(f"   {ack}")


if __name__ == "__main__":
    asyncio.run(main())

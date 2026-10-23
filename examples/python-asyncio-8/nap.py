"""asyncio.sleep, rebuilt from the two pieces of the last parts: a Future and call_later."""

import asyncio


async def nap(seconds, result=None):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    handle = loop.call_later(seconds, fut.set_result, result)  # a timer fills the box
    try:
        return await fut  # the coroutine is parked until the box is filled
    finally:
        handle.cancel()  # no effect if the timer already ran


async def main():
    loop = asyncio.get_running_loop()
    start = loop.time()
    price = await nap(0.12, 1199)
    print(f"{round((loop.time() - start) * 100) * 10} ms: nap returned {price:,}")


asyncio.run(main())

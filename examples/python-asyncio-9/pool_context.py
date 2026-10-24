"""Which request id does a pool thread see? It depends on the build, unless you pass the context."""

import asyncio
import contextvars
import functools
import sys
from concurrent.futures import ThreadPoolExecutor

from request_log import request_id


def sdk_call(item):
    return request_id.get()  # what a log line written by the SDK would be tagged with


async def handle(shopper, pool, carry):
    request_id.set(shopper)
    loop = asyncio.get_running_loop()
    call = functools.partial(sdk_call, "kettle-1l")
    if carry:
        call = functools.partial(contextvars.copy_context().run, call)
    return await loop.run_in_executor(pool, call)


async def main():
    gil = "GIL enabled" if sys._is_gil_enabled() else "free-threaded"
    print(f"{gil} build; sys.flags.thread_inherit_context = {sys.flags.thread_inherit_context}")
    for carry in (False, True):
        with ThreadPoolExecutor(max_workers=1) as pool:  # one worker, started by the first call
            seen = [await handle(f"shopper-{n}", pool, carry) for n in (1, 2, 3)]
        how = "run_in_executor + copy_context().run" if carry else "run_in_executor"
        print(f"  {how:37} shoppers 1, 2, 3 -> the SDK sees {', '.join(seen)}")


if __name__ == "__main__":
    asyncio.run(main())

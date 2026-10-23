"""Two requests at once: every log line carries its own request's id, in Tasks and in threads."""

import asyncio
import contextvars
import functools
import logging
from concurrent.futures import ThreadPoolExecutor

from request_log import capture, request_id

log = logging.getLogger("gateway")
sdk_log = logging.getLogger("seller_e_sdk")


def sdk_get_price(item):  # seller-e's sync SDK, in a thread; it logs like any library
    sdk_log.info("get_price %s", item)
    return 1149


async def ask(name, ms):
    log.info("asking %s", name)  # a child Task: it runs in a copy of the request's context
    await asyncio.sleep(ms / 1000)
    log.info("%s answered", name)


async def handle(shopper, pool, how):
    request_id.set(shopper)  # once, at the edge
    async with asyncio.TaskGroup() as tg:
        tg.create_task(ask("seller-a", 80))
        tg.create_task(ask("seller-b", 120))
    loop = asyncio.get_running_loop()
    if how == "run_in_executor":
        await loop.run_in_executor(pool, sdk_get_price, "kettle-1l")
    elif how == "copy_context().run":
        ctx = contextvars.copy_context()
        await loop.run_in_executor(pool, functools.partial(ctx.run, sdk_get_price, "kettle-1l"))
    log.info("answer sent")


async def main():
    lines = capture("gateway", "seller_e_sdk")
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="seller-e-sdk") as pool:
        for how in ("run_in_executor", "copy_context().run"):
            lines.lines.clear()
            async with asyncio.TaskGroup() as tg:
                tg.create_task(handle("shopper-1", pool, how))
                tg.create_task(handle("shopper-2", pool, how))
            print(f"-- seller-e's SDK called with {how} --")
            print("\n".join(sorted(lines.lines, key=lambda line: line.split("]")[0])))


if __name__ == "__main__":
    asyncio.run(main())

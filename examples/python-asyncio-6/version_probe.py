"""Three cancellation details that changed between Python 3.11 and 3.14. Run it on each version."""

import asyncio
import gc
import sys


async def withdrawn_before_delivery():
    me = asyncio.current_task()
    me.cancel()  # requested while the Task runs, so not delivered yet
    me.uncancel()  # withdrawn before the next await
    try:
        await asyncio.sleep(0.01)
        return "the next await ran normally"
    except asyncio.CancelledError:
        return "CancelledError arrived at the next await anyway"


async def stale_count_then_group():
    me = asyncio.current_task()
    asyncio.get_running_loop().call_later(0.01, me.cancel)
    try:  # noqa: SIM105 (written out on purpose: this is the refusal)
        await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass  # refused, without uncancel()

    async def fails():
        raise ValueError("bad price")

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fails())
            await asyncio.sleep(1)
    except* ValueError:
        pass
    try:
        await asyncio.sleep(0)
        return "handled the ValueError and carried on"
    except asyncio.CancelledError:
        return "CancelledError at the next await after the group"


async def shielded_failure_after_caller_left():
    reports = []
    asyncio.get_running_loop().set_exception_handler(lambda _loop, ctx: reports.append(ctx["message"]))

    async def write():
        await asyncio.sleep(0.02)
        raise ConnectionError("audit store down")

    async def handler():
        await asyncio.shield(write())  # nobody else holds the inner Task

    task = asyncio.create_task(handler())
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.sleep(0.03)
    gc.collect()  # in case the inner Task is still alive somewhere
    await asyncio.sleep(0)
    return f"asyncio reported {reports}"


async def hang_up_while_group_cleans_up():
    async def bad_seller():
        await asyncio.sleep(0.005)
        raise ValueError("price '12x9' is not a number")

    async def slow_seller():
        try:
            await asyncio.sleep(1)
        finally:
            await asyncio.sleep(0.02)  # its clean-up takes 20 ms

    me = asyncio.current_task()
    asyncio.get_running_loop().call_later(0.015, me.cancel)  # the shopper hangs up during that clean-up
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(bad_seller())
            tg.create_task(slow_seller())
            await asyncio.sleep(1)
    except* ValueError:
        pass  # answer "502"
    try:
        await asyncio.sleep(0.02)  # write the audit row
        return "wrote the audit row: the hang-up was lost"
    except asyncio.CancelledError:
        return "CancelledError at the audit write: the hang-up was kept"


async def main():
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    print("1. cancel() then uncancel() before any await:", await withdrawn_before_delivery())
    print(
        "2. a refused cancel, then a failing TaskGroup:", await asyncio.create_task(stale_count_then_group())
    )
    print("3. a shielded write fails after its caller left:", await shielded_failure_after_caller_left())
    task = asyncio.create_task(hang_up_while_group_cleans_up())
    await asyncio.wait([task])
    result = "the request ended cancelled" if task.cancelled() else task.result()
    print("4. a hang-up while a failing group cleans up:", result)


asyncio.run(main())

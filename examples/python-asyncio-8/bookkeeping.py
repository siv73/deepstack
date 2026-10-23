"""cancelling() counts cancel requests; timeout and TaskGroup use it to tell their own from others'."""

import asyncio


def count():
    return asyncio.current_task().cancelling()


async def deadline_alone():
    print(f"before the block: cancelling={count()}")
    try:
        async with asyncio.timeout(0.05):
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                print(f"inside, as the deadline fires: cancelling={count()}")
                raise
    except TimeoutError:
        print(f"outside: TimeoutError, cancelling={count()}")


async def deadline_and_hang_up():
    me = asyncio.current_task()
    try:
        async with asyncio.timeout(0.05) as cm:
            loop = asyncio.get_running_loop()
            loop.call_at(cm.when(), me.cancel)  # the shopper hangs up at the same moment
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                print(f"inside, two requests: cancelling={count()}")
                raise
    except TimeoutError:
        print("outside: TimeoutError")
    except asyncio.CancelledError:
        print(f"outside: CancelledError, not TimeoutError; cancelling={count()}")
        raise  # the shopper's cancellation travels on


async def bad_seller():
    raise ValueError("price '12x9' is not a number")


async def group_cancels_its_body():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(bad_seller())
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                print(f"body interrupted by its own group: cancelling={count()}")
                raise
    except* ValueError:
        print(f"outside: ExceptionGroup(ValueError) handled; cancelling={count()}")


async def main():
    print("-- 1. a deadline fires --")
    await deadline_alone()
    print("-- 2. the deadline fires and the shopper hangs up in the same loop turn --")
    task = asyncio.create_task(deadline_and_hang_up())
    await asyncio.wait([task])
    print(f"the request's Task ends cancelled={task.cancelled()}")
    print("-- 3. a task in a TaskGroup fails --")
    await group_cancels_its_body()


asyncio.run(main())

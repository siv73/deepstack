"""cancel() only asks: a Task right after cancel(), and one turn of the loop later."""

import asyncio


async def seller_e():
    try:
        await asyncio.sleep(0.9)  # stands in for seller-e's 900 ms answer
        return 1149
    finally:
        print("  seller-e: finally runs (its connection would be closed here)")


def state(task):
    return f"done={task.done()}, cancelled={task.cancelled()}, cancelling={task.cancelling()}"


async def main():
    task = asyncio.create_task(seller_e())
    await asyncio.sleep(0.25)  # the 250 ms deadline
    print("cancel() returned", task.cancel())
    print("right after cancel():", state(task))
    await asyncio.sleep(0)  # give the loop one turn
    print("one loop turn later: ", state(task))
    print("cancel() again returned", task.cancel())


asyncio.run(main())

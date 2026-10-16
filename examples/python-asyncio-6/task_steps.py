"""A Task drives its coroutine one step at a time and parks it on a Future in between."""

import asyncio


class LoudFuture(asyncio.Future):
    """A Future that reports when someone subscribes to it or fills it."""

    def add_done_callback(self, fn, *, context=None):
        print(f"{clock():4} ms  Future: a done callback was added (the Task's wake-up)")
        super().add_done_callback(fn, context=context)

    def set_result(self, result):
        print(f"{clock():4} ms  Future: set_result({result}) called by the timer")
        super().set_result(result)


async def ask_seller_b():
    print(f"{clock():4} ms  step 1: coroutine starts and awaits a Future")
    fut = LoudFuture(loop=loop)
    loop.call_later(0.12, fut.set_result, 1199)  # stands in for seller-b's socket
    price = await fut
    print(f"{clock():4} ms  step 2: coroutine resumed with {price:,}")
    return price


loop = asyncio.new_event_loop()
start = loop.time()


def clock():
    return round((loop.time() - start) * 100) * 10


task = loop.create_task(ask_seller_b(), name="seller-b")
print(f"{clock():4} ms  create_task: scheduled, not started (done={task.done()})")
result = loop.run_until_complete(task)
print(f"{clock():4} ms  Task done: result {result:,}")
loop.close()

"""Part 2's Task trace, with a cancel at the deadline: where the CancelledError comes from."""

import asyncio


class LoudFuture(asyncio.Future):
    """A Future that reports who subscribes to it, fills it, or cancels it."""

    def add_done_callback(self, fn, *, context=None):
        print(f"{clock():4} ms  Future: a done callback was added (the Task's wake-up)")
        super().add_done_callback(fn, context=context)

    def cancel(self, msg=None):
        print(f"{clock():4} ms  Future: cancel() called by the Task, msg={msg!r}")
        return super().cancel(msg=msg)


async def ask_seller_e():
    fut = LoudFuture(loop=loop)  # stands in for the reader's waiter on seller-e's socket
    print(f"{clock():4} ms  step 1: coroutine awaits the Future")
    try:
        return await fut
    except asyncio.CancelledError as exc:
        print(f"{clock():4} ms  step 2: CancelledError{exc.args} thrown in at the await")
        raise
    finally:
        print(f"{clock():4} ms  step 2: finally runs; the coroutine ends")


def deadline():
    print(f"{clock():4} ms  deadline timer: task.cancel() returned {task.cancel('deadline')}")
    print(f"{clock():4} ms  deadline timer: task.done()={task.done()}, cancelling()={task.cancelling()}")


loop = asyncio.new_event_loop()
start = loop.time()


def clock():
    return round((loop.time() - start) * 100) * 10


task = loop.create_task(ask_seller_e(), name="seller-e")
loop.call_later(0.25, deadline)
try:
    loop.run_until_complete(task)
except asyncio.CancelledError as exc:
    print(f"{clock():4} ms  the awaiter gets CancelledError{exc.args}; task.cancelled()={task.cancelled()}")
loop.close()

"""Touching asyncio objects from the wrong thread, or from the wrong loop."""

import asyncio
import re
import threading
import time

shared_lock = asyncio.Lock()  # module level: outlives any one event loop


def sdk_thread(deliver):
    time.sleep(0.1)  # the SDK's answer arrives on its own thread, 100 ms in
    try:
        deliver()
    except RuntimeError as e:
        print(f"  in the SDK's thread: RuntimeError: {e}")


async def wait_for_answer(how, debug=False):
    loop = asyncio.get_running_loop()
    loop.set_debug(debug)
    fut = loop.create_future()
    keepalive = loop.call_later(1.0, lambda: None)  # the loop's only timer: 1 s away
    if how == "set_result":
        deliver = lambda: fut.set_result(1149)  # noqa: E731
    else:
        deliver = lambda: loop.call_soon_threadsafe(fut.set_result, 1149)  # noqa: E731
    start = loop.time()
    threading.Thread(target=sdk_thread, args=(deliver,)).start()
    await asyncio.wait({fut}, timeout=1.5)  # returns when fut's done callbacks run, or at 1.5 s
    took = round((loop.time() - start) * 100) * 10
    print(f"  {how:20}  waiter woken at {took:4} ms; Future done: {fut.done()}")
    keepalive.cancel()


async def contended():
    async def holder():
        async with shared_lock:
            await asyncio.sleep(0.01)

    async with asyncio.TaskGroup() as tg:  # two Tasks at once: the second must wait
        tg.create_task(holder())
        tg.create_task(holder())


def main():
    print("-- the SDK's thread completes an asyncio Future --")
    asyncio.run(wait_for_answer("set_result"))
    asyncio.run(wait_for_answer("call_soon_threadsafe"))
    print("-- the same set_result() in debug mode --")
    asyncio.run(wait_for_answer("set_result", debug=True))
    print("-- one module-level Lock, used by two event loops in turn --")
    asyncio.run(contended())
    print("  loop 1: two Tasks shared the lock")
    try:
        asyncio.run(contended())
    except* RuntimeError as group:
        message = re.sub(r" object at 0x[0-9a-f]+", "", str(group.exceptions[0]))  # drop the address
        print(f"  loop 2: RuntimeError: {message}")


if __name__ == "__main__":
    main()

"""Trap 3a: which fire-and-forget Tasks can disappear? Three Tasks, no references kept."""

import asyncio
import gc


async def on_a_timer(log):
    await asyncio.sleep(0.05)  # the loop's timer heap holds the way to wake it
    log.append("timer task: finished")


async def on_an_event(log, event):
    await event.wait()  # the Event, which main() keeps, holds the way to wake it
    log.append("event task: finished")


async def on_its_own_future(log):
    fut = asyncio.get_running_loop().create_future()  # nobody else can ever complete it
    try:
        await fut
    finally:
        log.append("orphan task: its finally ran, inside gc.collect()")


async def main():
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(lambda _loop, context: print("asyncio:", context["message"]))
    log, event = [], asyncio.Event()
    asyncio.create_task(on_a_timer(log))  # no reference kept
    asyncio.create_task(on_an_event(log, event))  # no reference kept
    asyncio.create_task(on_its_own_future(log))  # no reference kept
    await asyncio.sleep(0)  # let all three reach their await
    print("Tasks alive before gc.collect():", len(asyncio.all_tasks()) - 1)
    gc.collect()
    print("Tasks alive after gc.collect(): ", len(asyncio.all_tasks()) - 1)
    event.set()
    await asyncio.sleep(0.1)
    print("\n".join(log))


if __name__ == "__main__":
    asyncio.run(main())

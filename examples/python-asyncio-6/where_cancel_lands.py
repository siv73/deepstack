"""Where the CancelledError lands depends on what the Task is doing when cancel() is called."""

import asyncio


async def body(log):
    log.append("body started")
    await asyncio.sleep(1)
    log.append("after the await")


async def returns_without_waiting(log):
    asyncio.current_task().cancel()  # cancelled while it is running, as a TaskGroup does to its parent
    log.append("still running: cancel() cannot interrupt plain code")
    return "a value"


async def run(case, coro_fn, cancel_after_a_turn):
    log = []
    task = asyncio.create_task(coro_fn(log))
    if cancel_after_a_turn:
        await asyncio.sleep(0)  # let the Task take its first step and park at its await
        task.cancel()
    elif coro_fn is body:
        task.cancel()  # before the Task's first step
    await asyncio.wait([task])
    print(f"{case:<34} log={log}; cancelled={task.cancelled()}")


async def main():
    await run("1. parked at an await", body, True)
    await run("2. cancelled before its first step", body, False)
    await run("3. cancelled while running", returns_without_waiting, False)


asyncio.run(main())

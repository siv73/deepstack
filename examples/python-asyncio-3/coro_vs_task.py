"""Awaiting a coroutine runs it now, inside the caller; a Task runs when the loop gets a turn."""

import asyncio


async def note(log, word):
    log.append(word)


async def main():
    log = []
    task = asyncio.create_task(note(log, "task"))  # only scheduled: a step in the ready queue
    log.append("after create_task")
    await note(log, "coroutine")  # runs here and now; the loop is not involved
    log.append("after await coroutine")
    await asyncio.sleep(0)  # the first real pause: the loop runs the Task's first step
    log.append("after sleep(0)")
    await task
    for i, word in enumerate(log, 1):
        print(i, word)

    coro = note(log, "x")
    wrapped = asyncio.create_task(coro)
    print(type(coro).__name__, "is wrapped in a", type(wrapped).__name__)
    await wrapped


if __name__ == "__main__":
    asyncio.run(main())

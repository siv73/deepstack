"""The lost update fixed with asyncio.Lock: read, await and write become one step for other Tasks."""

import asyncio
import re

from race_counter import CallCounter


class LockedCounter(CallCounter):
    def __init__(self, trace=None):
        super().__init__(trace)
        self.lock = asyncio.Lock()

    async def record(self, name):
        async with self.lock:  # only one Task at a time runs this block
            await self.record_racy(name)  # the same read, await, write as before


def state(lock):
    return re.sub(r" object at 0x[0-9a-f]+", "", repr(lock))  # drop the address, which differs per run


async def count(tasks, trace=None):
    counter = LockedCounter(trace)
    async with asyncio.TaskGroup() as tg:
        for n in range(1, tasks + 1):
            tg.create_task(counter.record(f"task-{n}"))
        await asyncio.sleep(0)  # let every Task take its first step
        if trace is not None:
            trace.append(f"after one turn: {state(counter.lock)}")
    return counter.calls


if __name__ == "__main__":
    trace = []
    calls = asyncio.run(count(3, trace))
    print("-- 3 calls recorded at once, under one Lock --")
    print("\n".join(trace))
    print(f"3 calls made, counter = {calls}")
    print(f"-- 10 calls --\ncounter = {asyncio.run(count(10))}")

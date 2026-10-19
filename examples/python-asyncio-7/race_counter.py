"""A lost update on one thread: read a shared value, await something, then write."""

import asyncio


class CallCounter:
    """How many calls the gateway made to seller-d today. Its contract allows 1,500 a day."""

    def __init__(self, trace=None):
        self.calls = 0
        self.trace = trace

    async def record_racy(self, name):
        seen = self.calls  # 1. read
        self._note(f"{name} reads {seen}")
        await asyncio.sleep(0.001)  # 2. an await: a write to the metrics store, say
        self.calls = seen + 1  # 3. write a value computed from what it read before the await
        self._note(f"{name} writes {seen + 1}")

    async def record_no_await(self, name):
        self.calls += 1  # read and write with no await between: nothing else can run here

    def _note(self, line):
        if self.trace is not None:
            self.trace.append(line)


async def count(method, tasks, trace=None):
    counter = CallCounter(trace)
    async with asyncio.TaskGroup() as tg:
        for n in range(1, tasks + 1):
            tg.create_task(getattr(counter, method)(f"task-{n}"))
    return counter.calls


if __name__ == "__main__":
    trace = []
    calls = asyncio.run(count("record_racy", 3, trace))
    print("-- 3 calls recorded at once: read, await, write --")
    print("\n".join(trace))
    print(f"3 calls made, counter = {calls}")
    print("-- 10 calls --")
    print(f"read, await, write:   counter = {asyncio.run(count('record_racy', 10))}")
    print(f"no await in between:  counter = {asyncio.run(count('record_no_await', 10))}")

"""A toy event loop for coroutines: a ready queue, a timer heap and a virtual clock.

Time is virtual: waiting is free and makes the clock jump. Code that actually runs
(including a blocking call) costs real time, which is measured and added to the clock.
"""

import heapq
import time
from collections import deque


class Sleep:
    """An awaitable. Its __await__ yields a request that travels up to the loop."""

    def __init__(self, ms):
        self.ms = ms

    def __await__(self):
        yield ("sleep", self.ms)


async def sleep(ms):
    await Sleep(ms)


class Task:
    """A coroutine plus what the loop knows about it."""

    def __init__(self, coro, name):
        self.coro = coro
        self.name = name
        self.done = False
        self.result = None


class ToyLoop:
    def __init__(self, slow_ms=100):
        self.now = 0  # virtual clock, in ms
        self.ready = deque()  # tasks that can run now, first in first out
        self.timers = []  # heap of (wake_at, order, task)
        self.order = 0  # breaks ties between equal wake times
        self.slow_ms = slow_ms  # warn about any step that runs this long
        self.warnings = []
        self.trace = []  # (now, what happened, ready names, timers) after each event

    def spawn(self, coro, name):
        task = Task(coro, name)
        self.ready.append(task)
        return task

    def run(self, until=None):
        """Run until no work is left, or until the clock reaches `until` ms."""
        while self.ready or self.timers:
            if until is not None and self.now >= until:
                return
            if not self.ready:  # nothing to run: jump to the earliest timer
                wake_at, _, task = self.timers[0]
                if until is not None and wake_at > until:
                    self.now = until  # the next wake-up is past the deadline
                    return
                heapq.heappop(self.timers)
                self.now = max(self.now, wake_at)
                self.ready.append(task)
                self._note(f"wake {task.name}")
                continue
            self._step(self.ready.popleft())

    def _step(self, task):
        started = time.perf_counter()
        try:
            request = task.coro.send(None)  # resume it until its next suspension
        except StopIteration as stop:
            task.done, task.result = True, stop.value
        finally:  # an exception from the task is not caught: it leaves run()
            cost = round((time.perf_counter() - started) * 100) * 10  # nearest 10 ms
            self.now += cost
            if cost >= self.slow_ms:
                self.warnings.append(f"slow step: {task.name} ran for {cost} ms")
        if task.done:
            self._note(f"{task.name} finished")
            return
        if not (isinstance(request, tuple) and len(request) == 2 and request[0] == "sleep"):
            raise TypeError(f"toy loop cannot handle {request!r} from {task.name}")
        self.order += 1
        heapq.heappush(self.timers, (self.now + request[1], self.order, task))
        self._note(f"{task.name} sleeps {request[1]} ms")

    def _note(self, what):
        ready = [t.name for t in self.ready]
        timers = [(at, t.name) for at, _, t in sorted(self.timers)]
        self.trace.append((self.now, what, ready, timers))

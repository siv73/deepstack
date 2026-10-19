"""Toy loop, step 4: Part 1's ready queue and timer heap, plus a selector, on a real clock.

A task can now ask for three things: ("sleep", ms), ("read", sock) or ("write", sock).
Sockets are parked in the selector; timers in the heap; one select() call waits for both.
"""

import heapq
import selectors
import time
from collections import deque


class _Request:
    def __init__(self, kind, what):
        self.kind, self.what = kind, what

    def __await__(self):
        yield (self.kind, self.what)  # travels up to the loop, as in Part 1


async def sleep(ms):
    await _Request("sleep", ms)


async def readable(sock):
    await _Request("read", sock)


async def writable(sock):
    await _Request("write", sock)


class Task:
    def __init__(self, coro, name):
        self.coro, self.name = coro, name
        self.done, self.result = False, None
        self.sock = None  # the socket it is waiting on, if any


class IOLoop:
    def __init__(self):
        self.start = time.monotonic()
        self.ready = deque()
        self.timers = []  # heap of (wake_at_ms, order, task)
        self.order = 0
        self.selector = selectors.DefaultSelector()
        self.trace = []  # (ms, what happened)

    def elapsed(self):
        return (time.monotonic() - self.start) * 1000

    @property
    def now(self):  # rounded to the nearest 10 ms, like Part 1's clock
        return round(self.elapsed() / 10) * 10

    def spawn(self, coro, name):
        task = Task(coro, name)
        self.ready.append(task)
        return task

    def run(self, until=None):
        while self.ready or self.timers or self.selector.get_map():
            if until is not None and self.elapsed() >= until:
                return
            self._run_once(until)

    def _run_once(self, until):
        if self.ready:
            timeout = 0  # work is waiting: only peek at the sockets
        else:
            deadlines = [self.timers[0][0]] if self.timers else []
            if until is not None:
                deadlines.append(until)
            timeout = max(0, min(deadlines) - self.elapsed()) / 1000 if deadlines else None
        for key, _mask in self.selector.select(timeout):  # sleeps until a socket or timer is due
            task = key.data
            self.selector.unregister(key.fileobj)
            task.sock = None
            self.ready.append(task)
            self.trace.append((self.now, f"{task.name} socket ready"))
        while self.timers and self.timers[0][0] <= self.elapsed():
            _, _, task = heapq.heappop(self.timers)
            self.ready.append(task)
        for _ in range(len(self.ready)):  # run only what is ready now
            self._step(self.ready.popleft())

    def _step(self, task):
        try:
            kind, what = task.coro.send(None)
        except StopIteration as stop:
            task.done, task.result = True, stop.value
            self.trace.append((self.now, f"{task.name} finished"))
            return
        if kind == "sleep":
            self.order += 1
            heapq.heappush(self.timers, (self.elapsed() + what, self.order, task))
        else:
            event = selectors.EVENT_READ if kind == "read" else selectors.EVENT_WRITE
            self.selector.register(what, event, data=task)
            task.sock = what
        self.trace.append((self.now, f"{task.name} waits to {kind}"))

    def cancel(self, task):
        """Stop a waiting task: unregister its socket first, then close the coroutine."""
        if task.sock is not None:
            self.selector.unregister(task.sock)
            task.sock = None
        task.coro.close()  # GeneratorExit at its await; its finally closes the socket

    def close(self):
        self.selector.close()

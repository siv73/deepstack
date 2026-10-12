"""Toy loop, step 2: generators ask to sleep; a timer heap and a clock wake them."""

import heapq
from collections import deque


class Loop:
    def __init__(self):
        self.now = 0  # virtual clock, in ms
        self.ready = deque()
        self.timers = []  # heap of (wake_at, order, generator)
        self.order = 0  # breaks ties between equal wake times

    def spawn(self, gen):
        self.ready.append(gen)

    def run(self):
        while self.ready or self.timers:
            if not self.ready:  # nothing to run: jump the clock to the next timer
                wake_at, _, gen = heapq.heappop(self.timers)
                self.now = wake_at
                self.ready.append(gen)
                continue
            gen = self.ready.popleft()
            try:
                ms = next(gen)  # the generator yields how long it wants to sleep
            except StopIteration:
                continue
            self.order += 1
            heapq.heappush(self.timers, (self.now + ms, self.order, gen))


def sleeper(loop, name, waits):
    for ms in waits:
        print(f"{loop.now:4} ms  {name} sleeps {ms} ms")
        yield ms
    print(f"{loop.now:4} ms  {name} done")


if __name__ == "__main__":
    loop = Loop()
    loop.spawn(sleeper(loop, "A", [30, 50]))
    loop.spawn(sleeper(loop, "B", [20]))
    loop.spawn(sleeper(loop, "C", [40]))
    loop.run()

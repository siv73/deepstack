"""Toy loop, step 1: a ready queue that gives each generator a turn."""

from collections import deque


def counter(name, n):
    for i in range(1, n + 1):
        print(f"{name}: step {i}")
        yield  # give the turn back to the loop


def run(generators):
    ready = deque(generators)
    while ready:
        gen = ready.popleft()  # next in line
        try:
            next(gen)  # run it until its next yield
        except StopIteration:
            continue  # finished: do not put it back
        ready.append(gen)  # not finished: back of the line


if __name__ == "__main__":
    run([counter("A", 3), counter("B", 2)])

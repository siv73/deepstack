"""Watch asyncio's loop iterate: a selector that prints every select() call."""

import asyncio

from tracing import TracingSelector

loop = asyncio.SelectorEventLoop(TracingSelector())


def a():
    print("a runs and schedules c")
    loop.call_soon(c)


def b():
    print("b runs")


def c():
    print("c runs")


def timer():
    print("timer (100 ms) runs and stops the loop")
    loop.stop()


loop.call_later(0.1, timer)
loop.call_soon(a)
loop.call_soon(b)
loop.run_forever()
loop.close()

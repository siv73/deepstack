"""Calling an async def function runs nothing; send(None) runs it."""


async def greet(name):
    print(f"hello, {name}")
    return len(name)


coro = greet("asha")  # builds a coroutine object; the body has not run
print("created:", type(coro).__name__)
try:
    coro.send(None)  # what an event loop does: start or resume it
except StopIteration as stop:
    print("returned:", stop.value)

other = greet("ravi")
try:
    next(other)  # unlike a generator, a coroutine is not an iterator
except TypeError as error:
    print("TypeError:", error)
other.close()  # we never meant to run it; closing it avoids a warning

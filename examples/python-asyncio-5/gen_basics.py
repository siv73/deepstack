"""A generator pauses at every yield and keeps its local variables."""


def countdown(n):
    print("starting")
    while n > 0:
        yield n
        n -= 1
    return "lift-off"


gen = countdown(3)
print(type(gen).__name__)
print(next(gen))
print(next(gen))
print(next(gen))
try:
    next(gen)
except StopIteration as stop:
    print("finished, value =", stop.value)

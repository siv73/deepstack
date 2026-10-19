"""Two coroutines on the toy loop: their waits overlap on one thread."""

from toyloop import ToyLoop, sleep


async def cook(loop, dish, ms):
    print(f"{loop.now:4} ms  {dish} starts, waits {ms} ms")
    await sleep(ms)
    print(f"{loop.now:4} ms  {dish} ready")
    return dish


loop = ToyLoop()
tea = loop.spawn(cook(loop, "tea", 30), "tea")
eggs = loop.spawn(cook(loop, "eggs", 20), "eggs")
loop.run()
print(f"results: {tea.result}, {eggs.result}; clock: {loop.now} ms")
for now, what, ready, timers in loop.trace:
    print(f"{now:4} | {what:<17} | ready {ready} | timers {timers}")

"""Async generators finalized outside the loop that should run their clean-up.

1. The asyncio docs' own example: the generator is dropped while no loop is running.
2. A generator first iterated on one loop and dropped while another loop runs: its clean-up
   runs later, on the first loop, not on the loop that dropped it.
"""

import asyncio
import gc
import sys

sys.unraisablehook = lambda u: print(f"  ignored: {type(u.exc_value).__name__}: {u.exc_value}")
loops = {}  # loop -> a short name, for printing


def where():
    try:
        return loops[asyncio.get_running_loop()]
    except RuntimeError:
        return "no running loop"


async def prices(tag):
    try:
        yield 1199
        yield 1229
    finally:
        print(f"  {tag}: finally starts, on {where()}")
        await asyncio.sleep(0)  # async clean-up, such as closing a connection
        print(f"  {tag}: finally done")


print("-- 1. dropped while no loop is running --")
with asyncio.Runner() as runner:
    loops[runner.get_loop()] = "the runner's loop"
    gen = prices("gen 1")
    print(f"  first price: {runner.run(anext(gen))}")
    del gen  # the loop exists but is not running: nothing can run the async finally
    gc.collect()
    print("  generator dropped")

print("-- 2. first iterated on loop 1, dropped while loop 2 runs --")
kept = []


async def first_iteration():
    kept.append(prices("gen 2"))
    print(f"  first price: {await anext(kept[0])}")


async def drop_it():
    kept.clear()
    gc.collect()
    await asyncio.sleep(0.01)
    print("  loop 2: generator dropped; loop 2 finishes")


loop_one = asyncio.Runner()
loops[loop_one.get_loop()] = "loop 1"
loop_one.run(first_iteration())
with asyncio.Runner() as loop_two:
    loops[loop_two.get_loop()] = "loop 2"
    loop_two.run(drop_it())
print("  closing loop 1")
loop_one.close()

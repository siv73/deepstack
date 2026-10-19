"""asyncio.Barrier (3.11+): N Tasks wait until all N have arrived, then go on together."""

import asyncio
import re

start = 0.0


def ms():
    return round((asyncio.get_running_loop().time() - start) * 100) * 10


def state(b):
    return re.sub(r"<asyncio.locks.Barrier object at 0x[0-9a-f]+ (.*)>", r"\1", repr(b))


async def shopper(name, connect_ms, gate):
    await asyncio.sleep(connect_ms / 1000)  # opening its connection
    print(f"{ms():4} ms  {name} connected, waits at the barrier")
    position = await gate.wait()
    print(f"{ms():4} ms  {name} sends its request (position {position})")


async def main():
    global start
    start = asyncio.get_running_loop().time()
    gate = asyncio.Barrier(3)  # a load test: three shoppers must fire at the same instant
    async with asyncio.TaskGroup() as tg:
        for n, connect in enumerate([0, 30, 70], start=1):
            tg.create_task(shopper(f"shopper-{n}", connect, gate))
        await asyncio.sleep(0.05)
        print(f"{ms():4} ms  barrier: {state(gate)}")
    print(f"after:    barrier: {state(gate)}")

    print("-- shopper-3 cannot connect: abort() --")
    gate = asyncio.Barrier(3)
    waiting = [asyncio.create_task(gate.wait()) for _ in range(2)]
    await asyncio.sleep(0)
    await gate.abort()
    for task in waiting:
        try:
            await task
        except asyncio.BrokenBarrierError as e:
            print(f"waiting shopper: BrokenBarrierError: {e}")
    print(f"barrier: {state(gate)}")


if __name__ == "__main__":
    asyncio.run(main())

"""asyncio.Queue without and with a size limit: what put and get do when they cannot go ahead."""

import asyncio


async def main():
    line = asyncio.Queue()  # maxsize=0: no limit
    for n in range(100_000):
        line.put_nowait(f"request-{n}")
    print(f"no limit: maxsize={line.maxsize}, qsize={line.qsize():,}, full={line.full()}")

    line = asyncio.Queue(maxsize=2)
    line.put_nowait("request-1")
    line.put_nowait("request-2")
    print(f"limit 2: qsize={line.qsize()}, full={line.full()}")
    try:
        line.put_nowait("request-3")
    except asyncio.QueueFull:
        print("put_nowait on a full queue: QueueFull, the caller decides what to do now")

    parked = asyncio.create_task(line.put("request-3"))  # put() waits for room instead
    await asyncio.sleep(0)
    print("put() on a full queue: waiting;", line)
    print("get:", await line.get())  # taking one item makes room
    await parked
    print("put() finished; queue now:", [line.get_nowait() for _ in range(line.qsize())])
    try:
        line.get_nowait()
    except asyncio.QueueEmpty:
        print("get_nowait on an empty queue: QueueEmpty")


asyncio.run(main())

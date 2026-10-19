"""seller-c fails at 150 ms. What do gather() and TaskGroup do with the other four calls?"""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers


async def with_gather(ports, start):
    tasks = [asyncio.create_task(ask_seller(start, n, p, "kettle-1l"), name=n) for n, p in ports.items()]
    try:
        await asyncio.gather(*tasks)
    except Exception as exc:
        print(f"{ms_since(start):5} ms  gather raised {type(exc).__name__}: {exc}")
    print("        still running:", [t.get_name() for t in tasks if not t.done()])
    return tasks


async def with_taskgroup(ports, start):
    tasks = []
    try:
        async with asyncio.TaskGroup() as tg:
            tasks += [tg.create_task(ask_seller(start, n, p, "kettle-1l"), name=n) for n, p in ports.items()]
    except* Exception as group:
        print(f"{ms_since(start):5} ms  TaskGroup raised {type(group).__name__}: {group.exceptions}")
    print("        still running:", [t.get_name() for t in tasks if not t.done()])
    print("        cancelled:", [t.get_name() for t in tasks if t.cancelled()])


async def main():
    with running_sellers(faulty={"seller-c"}) as ports:
        loop = asyncio.get_running_loop()
        print("-- gather() --")
        start = loop.time()
        leftovers = await with_gather(ports, start)
        await asyncio.wait(leftovers)  # watch what the "abandoned" calls do next
        print(f"{ms_since(start):5} ms  the last leftover finished")
        print("-- TaskGroup --")
        await with_taskgroup(ports, loop.time())


if __name__ == "__main__":
    asyncio.run(main())

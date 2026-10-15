"""TaskGroup: start the five seller Tasks, wait for all of them, and fail as a group."""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers


async def ask_all(ports):
    start = asyncio.get_running_loop().time()
    tasks = {}
    try:
        async with asyncio.TaskGroup() as tg:
            for name, port in ports.items():
                tasks[name] = tg.create_task(ask_seller(start, name, port, "kettle-1l"), name=name)
        # here every Task is done: the async with waited for all of them
        print(
            f"all done after {ms_since(start)} ms:",
            ", ".join(f"{t.result().price:,}" for t in tasks.values()),
        )
    except* Exception as group:
        print(f"{type(group).__name__} after {ms_since(start)} ms: {group.exceptions!r}")
        print("cancelled by the group:", [n for n, t in tasks.items() if t.cancelled()])


async def main():
    with running_sellers() as ports:
        print("-- TaskGroup, every seller answers --")
        await ask_all(ports)
    with running_sellers(faulty={"seller-c"}) as ports:
        print("-- TaskGroup, seller-c fails --")
        await ask_all(ports)


if __name__ == "__main__":
    asyncio.run(main())

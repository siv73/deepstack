"""asyncio.wait(): returns (done, pending) and leaves the pending Tasks running."""

import asyncio

from gateway_v3 import ask_seller, ms_since
from sellers_net import running_sellers


def names(tasks):
    return sorted(t.get_name() for t in tasks)


async def main():
    with running_sellers() as ports:
        start = asyncio.get_running_loop().time()
        tasks = [asyncio.create_task(ask_seller(start, n, p, "kettle-1l"), name=n) for n, p in ports.items()]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        print(f"{ms_since(start):5} ms  FIRST_COMPLETED: done {names(done)}")

        done, pending = await asyncio.wait(tasks, timeout=0.25)  # no TimeoutError is raised
        print(f"{ms_since(start):5} ms  timeout=0.25: done {names(done)}, pending {names(pending)}")
        print("        pending Tasks cancelled by wait()?", any(t.cancelled() for t in pending))
        for t in pending:
            t.cancel()  # our job, not wait()'s
        await asyncio.wait(pending)
        print("        after our cancel():", [t.get_name() for t in tasks if t.cancelled()])


if __name__ == "__main__":
    asyncio.run(main())

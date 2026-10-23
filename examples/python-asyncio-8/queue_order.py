"""The same three requests through Queue, LifoQueue and PriorityQueue: which comes out first."""

import asyncio
import itertools
from dataclasses import dataclass


@dataclass
class Request:  # deliberately not comparable: like most real request objects
    shopper: str


async def main():
    arrivals = ["shopper-1", "shopper-2", "shopper-3"]  # in this order
    for kind in (asyncio.Queue, asyncio.LifoQueue):
        q = kind()
        for name in arrivals:
            q.put_nowait(name)
        print(f"{kind.__name__:>13}:", [q.get_nowait() for _ in arrivals])

    q = asyncio.PriorityQueue()  # lowest first; shopper-2 is checking out, so priority 0
    for name, priority in zip(arrivals, (1, 0, 1), strict=True):
        q.put_nowait((priority, name))
    print("PriorityQueue:", [q.get_nowait()[1] for _ in arrivals])

    q = asyncio.PriorityQueue()
    q.put_nowait((1, Request("shopper-1")))
    try:
        q.put_nowait((1, Request("shopper-3")))  # same priority: the heap compares the Requests
    except TypeError as exc:
        print("equal priorities, objects that cannot be compared:", exc)
        print("  and yet qsize() is now", q.qsize(), "- the failed put left its item in the heap")

    q, order = asyncio.PriorityQueue(), itertools.count()  # a tie-breaker that is always comparable
    for name, priority in zip(arrivals, (1, 0, 1), strict=True):
        q.put_nowait((priority, next(order), Request(name)))
    print("with a counter:", [q.get_nowait()[2].shopper for _ in arrivals])


asyncio.run(main())

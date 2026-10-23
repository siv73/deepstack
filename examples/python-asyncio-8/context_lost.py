"""Shared work started from one request carries that request's context into everyone's logs."""

import asyncio
import contextvars
import logging

from request_log import capture, request_id

log = logging.getLogger("gateway")


async def fill(item, own_id):
    if own_id:
        request_id.set(f"fill {item}")  # the shared work names itself
    log.info("calling seller-e for %s", item)
    await asyncio.sleep(0.05)
    log.info("seller-e answered")
    return 1149


async def shopper(name, flights, item, fresh):
    request_id.set(name)
    task = flights.get(item)
    if task is None:  # the first shopper starts the shared call
        context = contextvars.Context() if fresh else None  # None: a copy of this shopper's context
        task = asyncio.create_task(fill(item, own_id=fresh), context=context)
        task.add_done_callback(lambda t: log.info("done callback: fill finished"))  # runs in THIS context
        flights[item] = task
    await asyncio.shield(task)
    log.info("got 1,149")


async def main():
    lines = capture("gateway")
    for fresh in (False, True):
        lines.lines.clear()
        flights = {}
        async with asyncio.TaskGroup() as tg:
            for n in (1, 2, 3):
                tg.create_task(shopper(f"shopper-{n}", flights, "kettle-1l", fresh))
        how = "fresh Context() and its own id" if fresh else "started in shopper-1's context"
        print(f"-- the shared fill, {how} --")
        print("\n".join(lines.lines))


if __name__ == "__main__":
    asyncio.run(main())

"""Keep a DB commit alive when the client disconnects mid-request."""

import asyncio

_pending: set[asyncio.Task] = set()


async def commit_order(db: list[str], order_id: str) -> None:
    await asyncio.sleep(0.05)  # stands in for the INSERT + COMMIT
    db.append(order_id)


async def create_order(db: list[str], order_id: str) -> str:
    task = asyncio.create_task(commit_order(db, order_id))
    _pending.add(task)  # shield() does not keep the task alive for you
    task.add_done_callback(_pending.discard)
    await asyncio.shield(task)  # a disconnect cancels this handler, not the commit
    return "201 Created"

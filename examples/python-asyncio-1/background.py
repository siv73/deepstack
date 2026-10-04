"""Fire-and-forget done safely: keep a strong reference and report failures."""

import asyncio
import logging

log = logging.getLogger("jobs")
_running: set[asyncio.Task] = set()


def _finished(task: asyncio.Task) -> None:
    _running.discard(task)  # drop our reference once it's done
    if not task.cancelled() and task.exception() is not None:
        log.error("background job %s failed", task.get_name(), exc_info=task.exception())


def spawn(coro, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _running.add(task)  # the loop only holds a weak reference
    task.add_done_callback(_finished)
    return task

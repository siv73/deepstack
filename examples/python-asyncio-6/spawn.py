"""Fire-and-forget done safely: keep a strong reference, and report every failure at once."""

import asyncio
import logging
from collections import Counter

log = logging.getLogger("gateway.background")
running = set()  # strong references: the loop itself keeps only weak ones
failures = Counter()  # background failures by task name, for a metric


def spawn(coro, *, name):
    task = asyncio.create_task(coro, name=name)
    running.add(task)
    task.add_done_callback(_finished)
    return task


def _finished(task):
    running.discard(task)  # done: drop our reference
    if task.cancelled():
        return
    exc = task.exception()  # reading it marks it retrieved
    if exc is not None:
        failures[task.get_name()] += 1
        log.error("background task %s failed: %s: %s", task.get_name(), type(exc).__name__, exc, exc_info=exc)

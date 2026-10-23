"""Offers as they arrive: an async generator over the five seller asks of one quick quote.

It starts one ask per seller and yields each offer as soon as that ask finishes. Its finally
cancels the asks still waiting and waits for them, so whoever stops reading early leaves
nothing behind, provided the generator is closed when they stop.
"""

import asyncio
import logging

log = logging.getLogger("gateway")


async def offers(ask, ports, item):
    """Yield each seller's offer, fastest first. `ask(name, port)` is a coroutine function."""
    asks = [asyncio.create_task(ask(name, port), name=f"ask {name}") for name, port in ports.items()]
    try:
        for next_done in asyncio.as_completed(asks):
            result = await next_done
            if not isinstance(result, BaseException):  # timeouts and failures are values, not offers
                yield result
    finally:
        waiting = [t for t in asks if not t.done()]
        for task in waiting:
            task.cancel()
        if waiting:
            await asyncio.wait(waiting)  # their own clean-up, inside this generator's
        log.info("offer stream closed: %d asks cancelled", len(waiting))

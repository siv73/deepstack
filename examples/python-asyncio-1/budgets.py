"""A per-call time budget: give up on one slow dependency, keep serving."""

import asyncio


async def call_with_budget(fetch, url: str, budget: float) -> bytes | None:
    try:
        async with asyncio.timeout(budget):
            return await fetch(url)  # cancelled if the budget runs out
    except TimeoutError:  # only catchable here, outside the block
        return None  # caller picks: fallback, retry, or a 504

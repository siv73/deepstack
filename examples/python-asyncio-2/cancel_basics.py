"""What cancel() does: it asks. The task decides at its next await."""

import asyncio


async def polite(log: list[str]) -> None:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        log.append("rolled back")  # clean up...
        raise  # ...then let the cancellation continue


async def stubborn(log: list[str]) -> str:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        log.append("ignored the cancel")  # denies the request
    return "finished anyway"

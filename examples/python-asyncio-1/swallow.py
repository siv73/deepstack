"""Two workers under a timeout: one swallows cancellation, one cleans up and lets it go."""

import asyncio


async def swallowing_worker(rounds: int, errors: list[str]) -> None:
    for _ in range(rounds):
        try:
            await asyncio.sleep(0.05)  # stands in for one poll of a queue
        except BaseException as e:  # "never crash the poller": also eats CancelledError
            errors.append(type(e).__name__)


async def good_worker(log: list[str]) -> None:
    try:
        await asyncio.sleep(10)
    except Exception:  # CancelledError is not an Exception, so it passes through
        log.append("never reached on cancel")
    finally:
        log.append("closed connection")  # cleanup runs, then cancellation continues

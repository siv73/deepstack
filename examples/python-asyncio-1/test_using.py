"""Rung 3 behaviours: time budgets and sync SDKs via to_thread."""

import asyncio
import time

import budgets
import pytest
import sync_sdk


async def slow(url: str) -> bytes:
    await asyncio.sleep(1)
    return b"late"


async def fast(url: str) -> bytes:
    await asyncio.sleep(0.01)
    return b"ok"


def test_budget_returns_value_when_fast():
    assert asyncio.run(budgets.call_with_budget(fast, "u", 0.5)) == b"ok"


def test_budget_gives_up_on_time():
    start = time.perf_counter()
    assert asyncio.run(budgets.call_with_budget(slow, "u", 0.05)) is None
    assert time.perf_counter() - start < 0.3


def test_timeout_error_cannot_be_caught_inside_the_block():
    caught_inside = []

    async def main():
        async with asyncio.timeout(0.05):
            try:
                await asyncio.sleep(1)
            except TimeoutError:
                caught_inside.append(True)

    with pytest.raises(TimeoutError):
        asyncio.run(main())
    assert caught_inside == []  # inside the block it is still a CancelledError


def test_to_thread_runs_sync_calls_side_by_side():
    start = time.perf_counter()
    out = asyncio.run(sync_sdk.get_many(["a", "b", "c", "d", "e"]))
    took = time.perf_counter() - start
    assert out == ["value:a", "value:b", "value:c", "value:d", "value:e"]
    assert took < 0.6  # about 0.2 s, not 5 x 0.2 = 1.0 s


def test_timeout_waits_for_slow_cleanup():
    async def slow_cleanup():
        try:
            await asyncio.sleep(10)
        finally:
            await asyncio.sleep(0.2)  # e.g. rolling back a transaction

    async def main():
        async with asyncio.timeout(0.05):
            await slow_cleanup()

    start = time.perf_counter()
    with pytest.raises(TimeoutError):
        asyncio.run(main())
    assert 0.24 <= time.perf_counter() - start < 0.5


def test_timeout_on_to_thread_leaves_the_thread_running():
    done: list[str] = []

    def sync_write() -> None:
        time.sleep(0.2)
        done.append("row written")

    async def main():
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                await asyncio.to_thread(sync_write)
        assert done == []  # the caller gave up...
        await asyncio.sleep(0.3)
        assert done == ["row written"]  # ...but the thread finished the write anyway

    asyncio.run(main())

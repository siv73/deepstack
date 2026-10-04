"""Behaviours from rungs 1-2: calling vs awaiting, sequential vs concurrent, who runs first."""

import asyncio
import gc
import inspect
import time
import warnings

import await_order
import not_awaited
import pytest
import sequential


def test_calling_creates_coroutine_object_and_runs_nothing():
    outbox: list[str] = []
    coro = not_awaited.send_receipt(outbox, 1)
    assert inspect.iscoroutine(coro)
    assert outbox == []
    coro.close()


def test_forgotten_await_does_nothing_and_warns():
    outbox: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        asyncio.run(not_awaited.checkout_buggy(outbox))
        gc.collect()
    assert outbox == []
    assert any(
        issubclass(w.category, RuntimeWarning) and "was never awaited" in str(w.message) for w in caught
    )


def test_fixed_checkout_sends():
    outbox: list[str] = []
    asyncio.run(not_awaited.checkout_fixed(outbox))
    assert outbox == ["receipt for 42"]


def _timed(coro) -> float:
    start = time.perf_counter()
    asyncio.run(coro)
    return time.perf_counter() - start


def test_sequential_awaits_add_up():
    assert 0.29 <= _timed(sequential.one_by_one([0.1, 0.2])) < 0.4


def test_taskgroup_takes_the_longest_not_the_sum():
    assert 0.19 <= _timed(sequential.together([0.1, 0.2])) < 0.28


def test_await_coroutine_does_not_yield_to_other_tasks():
    assert asyncio.run(await_order.run(wrap_in_task=False)) == ["a", "a", "a", "b"]


def test_await_task_yields_to_the_loop():
    assert asyncio.run(await_order.run(wrap_in_task=True)) == ["b", "a", "a", "a"]


def test_asyncio_run_inside_a_running_loop_raises():
    async def inner() -> int:
        return 1

    async def handler() -> None:
        coro = inner()
        try:
            asyncio.run(coro)
        finally:
            coro.close()

    with pytest.raises(RuntimeError):
        asyncio.run(handler())

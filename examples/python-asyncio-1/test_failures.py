"""Rung 4 behaviours: blocking the loop, lost tasks, gather vs TaskGroup, swallowed cancellation."""

import asyncio
import logging
import time

import background
import blocking
import gather_leak
import pytest
import swallow


def test_sync_sleep_freezes_every_other_task():
    assert asyncio.run(blocking.worst_heartbeat_delay(blocking.handler_blocking)) > 0.25


def test_to_thread_keeps_the_loop_responsive():
    assert asyncio.run(blocking.worst_heartbeat_delay(blocking.handler_fixed)) < 0.1


def test_debug_mode_logs_the_slow_step(caplog):
    caplog.set_level(logging.WARNING, logger="asyncio")
    asyncio.run(blocking.handler_blocking(), debug=True)
    assert any("Executing" in r.getMessage() and "took" in r.getMessage() for r in caplog.records)


def test_spawn_keeps_a_reference_until_done():
    async def main():
        t = background.spawn(asyncio.sleep(0.01), name="warm-cache")
        assert t in background._running
        await t
        await asyncio.sleep(0)
        assert t not in background._running

    asyncio.run(main())


def test_spawn_logs_failures(caplog):
    async def boom():
        raise RuntimeError("cache warm failed")

    async def main():
        background.spawn(boom(), name="warm-cache")
        await asyncio.sleep(0.01)

    caplog.set_level(logging.ERROR)
    asyncio.run(main())
    msgs = [r.getMessage() for r in caplog.records]
    assert "background job warm-cache failed" in msgs
    assert not any("never retrieved" in m for m in msgs)


def test_gather_raises_but_sibling_keeps_running():
    done: list[str] = []

    async def main():
        with pytest.raises(ValueError):
            await gather_leak.with_gather(done)
        assert done == []  # gather already raised...
        await asyncio.sleep(0.15)
        assert done == ["wrote row"]  # ...and the sibling still finished its write

    asyncio.run(main())


def test_taskgroup_cancels_sibling():
    done: list[str] = []

    async def main():
        with pytest.raises(ExceptionGroup):
            await gather_leak.with_taskgroup(done)
        await asyncio.sleep(0.15)
        assert done == []

    asyncio.run(main())


def test_swallowing_cancellation_breaks_the_timeout():
    errors: list[str] = []

    async def main():
        start = time.perf_counter()
        async with asyncio.timeout(0.05):  # no TimeoutError is raised at all
            await swallow.swallowing_worker(6, errors)
        return time.perf_counter() - start

    assert asyncio.run(main()) >= 0.29  # ran all 6 rounds, 6x past the deadline
    assert errors == ["CancelledError"]  # the timeout's cancel was caught and dropped


def test_good_worker_cleans_up_and_times_out():
    log: list[str] = []

    async def main():
        async with asyncio.timeout(0.05):
            await swallow.good_worker(log)

    with pytest.raises(TimeoutError):
        asyncio.run(main())
    assert log == ["closed connection"]


def test_cancelled_error_is_not_an_exception():
    assert issubclass(asyncio.CancelledError, BaseException)
    assert not issubclass(asyncio.CancelledError, Exception)


def test_timeout_cannot_fire_during_a_blocking_call():
    async def main():
        start = time.perf_counter()
        async with asyncio.timeout(0.05):
            time.sleep(0.3)  # stands in for a sync requests.get()
        return time.perf_counter() - start

    assert asyncio.run(main()) >= 0.3  # no TimeoutError: the timer never got a turn

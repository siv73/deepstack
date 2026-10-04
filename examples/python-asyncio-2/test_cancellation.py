"""Rung 2-3 behaviours: cancel is a request, uncancel bookkeeping, shield, contextvars."""

import asyncio
import sys

import cancel_basics
import commit
import pytest
import request_ctx
import stale_cancel


def test_cancel_returns_true_and_task_ends_cancelled():
    log: list[str] = []

    async def main():
        t = asyncio.create_task(cancel_basics.polite(log))
        await asyncio.sleep(0)
        assert t.cancel() is True
        assert not t.done()  # only a request so far
        with pytest.raises(asyncio.CancelledError):
            await t
        assert t.cancelled()

    asyncio.run(main())
    assert log == ["rolled back"]


def test_cancel_message_reaches_the_awaiter():
    async def main():
        t = asyncio.create_task(asyncio.sleep(10))
        await asyncio.sleep(0)
        t.cancel("deploy in progress")
        with pytest.raises(asyncio.CancelledError) as info:
            await t
        return info.value.args

    assert asyncio.run(main()) == ("deploy in progress",)


def test_cancel_before_first_step_means_body_never_runs():
    log: list[str] = []

    async def main():
        t = asyncio.create_task(cancel_basics.polite(log))
        t.cancel()  # before the task ever ran
        with pytest.raises(asyncio.CancelledError):
            await t

    asyncio.run(main())
    assert log == []  # not even the except block ran


def test_a_task_can_refuse_and_then_is_not_cancelled():
    log: list[str] = []

    async def main():
        t = asyncio.create_task(cancel_basics.stubborn(log))
        await asyncio.sleep(0)
        t.cancel()
        result = await t
        assert not t.cancelled()
        assert t.cancel() is False  # already done
        return result

    assert asyncio.run(main()) == "finished anyway"
    assert log == ["ignored the cancel"]


@pytest.mark.skipif(sys.version_info < (3, 13), reason="TaskGroup cancel-count handling changed in 3.13")
def test_refusing_without_uncancel_poisons_a_later_taskgroup():
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(stale_cancel.refuse_then_use_taskgroup(call_uncancel=False))


def test_uncancel_clears_the_record():
    assert asyncio.run(stale_cancel.refuse_then_use_taskgroup(call_uncancel=True)) == "done"


def test_shield_keeps_commit_running_after_handler_is_cancelled():
    db: list[str] = []

    async def main():
        h = asyncio.create_task(commit.create_order(db, "o-1"))
        await asyncio.sleep(0.01)
        h.cancel()  # client disconnected
        with pytest.raises(asyncio.CancelledError):
            await h  # the caller still sees the cancellation
        assert db == []
        await asyncio.sleep(0.1)
        assert db == ["o-1"]  # the commit finished anyway

    asyncio.run(main())


def test_shielded_work_is_still_cancelled_when_asyncio_run_exits():
    db: list[str] = []

    async def main():
        h = asyncio.create_task(commit.create_order(db, "o-2"))
        await asyncio.sleep(0.01)
        h.cancel()
        await asyncio.sleep(0)
        # main returns now; asyncio.run cancels every task still pending

    asyncio.run(main())
    assert db == []


def test_request_id_follows_each_request_and_does_not_leak():
    out: list[str] = []

    async def main():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(request_ctx.handle("req-A", out))
            tg.create_task(request_ctx.handle("req-B", out))

    asyncio.run(main())
    assert sorted(out) == sorted(
        [
            "[req-A] child",
            "[req-A] parent",
            "[req-A] thread",
            "[req-B] child",
            "[req-B] parent",
            "[req-B] thread",
        ]
    )

"""Part 2: the behaviours the page claims about sockets, selectors, the loop, Futures and Tasks."""

import asyncio
import contextlib
import errno
import io
import selectors
import socket
import sys
import time

import pytest
from sellers import BUDGET_MS
from sellers_net import running_sellers
from toyloop_io import IOLoop

LINUX = sys.platform.startswith("linux")


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


# ---- sockets and selectors -------------------------------------------------


def test_new_sockets_are_blocking_and_setblocking_false_means_timeout_zero():
    with socket.socket() as sock:
        assert sock.gettimeout() is None  # blocking mode (no default timeout set)
        sock.setblocking(False)
        assert sock.gettimeout() == 0.0


def test_recv_on_an_empty_nonblocking_socket_raises_blockingioerror():
    a, b = socket.socketpair()
    with a, b:
        a.setblocking(False)
        with pytest.raises(BlockingIOError) as info:
            a.recv(10)
        assert info.value.errno in (errno.EAGAIN, errno.EWOULDBLOCK)


def test_default_selector_prefers_kqueue_then_epoll():
    if hasattr(selectors, "KqueueSelector"):
        assert selectors.DefaultSelector is selectors.KqueueSelector
    elif LINUX:
        assert selectors.DefaultSelector is selectors.EpollSelector


def test_registering_the_same_socket_twice_is_a_keyerror():
    with selectors.DefaultSelector() as sel, socket.socket() as sock:
        sel.register(sock, selectors.EVENT_READ)
        with pytest.raises(KeyError):
            sel.register(sock, selectors.EVENT_READ)


def test_select_with_timeout_zero_does_not_wait():
    a, b = socket.socketpair()
    with selectors.DefaultSelector() as sel, a, b:
        sel.register(a, selectors.EVENT_READ)  # connected, but nothing sent: not ready
        start = time.monotonic()
        assert sel.select(timeout=0) == []
        assert time.monotonic() - start < 0.05


# ---- the loop, call_soon and call_later ---------------------------------------


def test_callbacks_added_while_running_wait_for_the_next_iteration():
    loop = asyncio.new_event_loop()
    order = []
    loop.call_soon(lambda: (order.append("a"), loop.call_soon(order.append, "c")))
    loop.call_soon(order.append, "b")
    loop.call_soon(loop.stop)  # stop after this iteration
    loop.run_forever()
    assert order == ["a", "b"]  # c was queued during the iteration: not run yet
    loop.call_soon(loop.stop)
    loop.run_forever()
    assert order == ["a", "b", "c"]
    loop.close()


def test_cancelled_handle_never_runs():
    loop = asyncio.new_event_loop()
    ran = []
    loop.call_later(0.01, ran.append, 1).cancel()
    loop.call_later(0.03, loop.stop)
    loop.run_forever()
    loop.close()
    assert ran == []


def test_loop_time_is_monotonic_clock():
    loop = asyncio.new_event_loop()
    assert abs(loop.time() - time.monotonic()) < 0.05
    loop.close()


# ---- Futures and Tasks --------------------------------------------------------


def test_done_callback_is_scheduled_not_called_inline():
    loop = asyncio.new_event_loop()
    fut, seen = loop.create_future(), []
    fut.add_done_callback(lambda f: seen.append(f.result()))
    fut.set_result(1199)
    assert seen == []  # scheduled with call_soon
    loop.call_soon(loop.stop)
    loop.run_forever()
    assert seen == [1199]
    loop.close()


def test_future_states_and_errors():
    loop = asyncio.new_event_loop()
    fut = loop.create_future()
    with pytest.raises(asyncio.InvalidStateError):
        fut.result()
    with pytest.raises(asyncio.InvalidStateError):
        fut.exception()
    fut.set_result(1)
    with pytest.raises(asyncio.InvalidStateError):
        fut.set_result(2)
    gone = loop.create_future()
    assert gone.cancel() is True and gone.cancel() is False
    with pytest.raises(asyncio.CancelledError):
        gone.result()
    with pytest.raises(asyncio.CancelledError):
        gone.exception()
    loop.close()


def test_awaiting_a_future_yields_the_future_itself():
    loop = asyncio.new_event_loop()
    fut = loop.create_future()

    async def use():
        return await fut

    coro = use()
    assert coro.send(None) is fut
    coro.close()
    loop.close()


def test_create_task_does_not_run_the_coroutine_until_the_loop_turns():
    loop = asyncio.new_event_loop()
    ran = []

    async def job():
        ran.append(True)

    task = loop.create_task(job())
    assert ran == [] and not task.done()
    loop.run_until_complete(task)
    assert ran == [True]
    loop.close()


def test_a_task_keeps_its_exception_and_others_are_unaffected():
    async def bad():
        raise ValueError("seller-c failed")

    async def good():
        await asyncio.sleep(0.01)
        return 1199

    async def main():
        t1, t2 = asyncio.create_task(bad()), asyncio.create_task(good())
        await asyncio.sleep(0.05)
        return t1, t2

    t1, t2 = asyncio.run(main())
    assert isinstance(t1.exception(), ValueError) and t2.result() == 1199


def test_bare_yield_via_sleep_zero_gives_up_one_iteration():
    order = []

    async def a():
        order.append("a1")
        await asyncio.sleep(0)
        order.append("a2")

    async def b():
        order.append("b1")

    async def main():
        await asyncio.gather(a(), b())

    asyncio.run(main())
    assert order == ["a1", "b1", "a2"]


# ---- asyncio.run ---------------------------------------------------------------


def test_asyncio_run_cannot_be_nested():
    async def inner():
        return 1

    async def outer():
        coro = inner()
        try:
            asyncio.run(coro)
        finally:
            coro.close()

    with pytest.raises(RuntimeError):
        asyncio.run(outer())


def test_asyncio_run_accepts_any_awaitable_on_314():
    class Ready:
        def __await__(self):
            return (yield from asyncio.sleep(0, result=7).__await__())

    assert asyncio.run(Ready()) == 7


def test_get_event_loop_without_a_loop_raises_on_314():
    with pytest.raises(RuntimeError):
        asyncio.get_event_loop()


def test_asyncio_run_cancels_leftovers_and_closes_the_loop():
    seen = {}

    async def leftover():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            seen["cancelled"] = True
            raise

    async def main():
        seen["task"] = asyncio.create_task(leftover())
        seen["loop"] = asyncio.get_running_loop()
        await asyncio.sleep(0)

    asyncio.run(main())
    assert seen["cancelled"] and seen["task"].cancelled() and seen["loop"].is_closed()


# ---- the toy selector loop ------------------------------------------------------


def test_toy_io_loop_cancel_unregisters_before_closing():
    from gateway_v2 import ask_seller

    with running_sellers() as ports:
        loop = IOLoop()
        tasks = [loop.spawn(ask_seller(loop, n, p, "kettle-1l"), n) for n, p in ports.items()]
        quiet(loop.run, until=BUDGET_MS)
        waiting = [t for t in tasks if not t.done]
        assert [t.name for t in waiting] == ["seller-e"]
        assert len(loop.selector.get_map()) == 1
        for t in waiting:
            loop.cancel(t)
        assert len(loop.selector.get_map()) == 0
        loop.close()


def test_toy_io_loop_trace_order():
    from gateway_v2 import compare

    with running_sellers() as ports:
        _, missed, loop = quiet(compare, ports, "kettle-1l", budget_ms=BUDGET_MS)
    events = [what for _, what in loop.trace]
    names = ["seller-a", "seller-b", "seller-c", "seller-d", "seller-e"]
    assert events[:15] == (
        [f"{n} waits to write" for n in names]
        + [f"{n} socket ready" for n in names]
        + [f"{n} waits to read" for n in names]
    )
    finished = [what.split()[0] for what in events if what.endswith("finished")]
    assert finished == names[:4] and missed == ["seller-e"]

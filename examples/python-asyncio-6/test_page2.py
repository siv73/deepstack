"""Part 2: the page shows what the code does, and every check's answer holds."""

import asyncio
import contextlib
import io
import json
import resource
import selectors
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import gateway_v1
import gateway_v2
import gateway_v3
import pytest
from sellers import BUDGET_MS, SELLERS, SellerError
from sellers_net import running_sellers

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-2"
BODY = (CONTENT / "body.html").read_text()
LINUX = sys.platform.startswith("linux")


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def test_measured_idle_costs_are_the_ones_the_page_shows():
    m = json.loads((HERE / "measured_idle.json").read_text())
    for row in m["rows"]:
        if row["select_us"] is not None:
            assert f"<td>about {row['select_us']} µs</td>" in BODY
        assert f"<td>about {row['epoll_us']} µs</td>" in BODY
    assert m["python"] in BODY and m["system"] in BODY


def test_meta_keeps_the_series_plan_and_links_both_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert meta["prereqs"][0]["slug"] == "python-asyncio-1"
    assert plan[1].get("slug") == "python-asyncio-2"
    page1 = (CONTENT.parent / "python-asyncio-1" / "body.html").read_text()
    assert '<a href="../python-asyncio-2/index.html">' in page1


def test_every_example_program_with_output_is_on_the_page():
    for out in (HERE / "out").glob("*.txt"):
        name = out.stem
        if f'data-file="{name}.py"' in BODY:
            assert f'data-file="out/{name}.txt"' in BODY, name


# ---- answers to the page's checks ---------------------------------------------


def test_predict_v2_with_160ms_budget():
    with running_sellers() as ports:
        best, missed, loop = quiet(gateway_v2.compare, ports, "kettle-1l", budget_ms=160)
    assert (best.seller, best.price) == ("seller-b", 1199)
    assert missed == ["seller-d", "seller-e"]


def test_predict_blocking_with_seller_e_first_has_nothing_at_250ms():
    with running_sellers() as ports:
        order = ["seller-e", "seller-a", "seller-b", "seller-c", "seller-d"]
        start, seen_by_budget = time.monotonic(), []
        for name in order:
            with socket.create_connection(("127.0.0.1", ports[name])) as sock:
                sock.sendall(b"kettle-1l\n")
                sock.recv(100)
            if time.monotonic() - start <= BUDGET_MS / 1000:
                seen_by_budget.append(name)
    assert seen_by_budget == []


def test_predict_future_set_exception_raises_at_the_await():
    loop = asyncio.new_event_loop()
    fut = loop.create_future()

    async def ask():
        return await fut

    coro = ask()
    coro.send(None)
    fut.set_exception(ValueError("seller-b down"))
    with pytest.raises(ValueError, match="seller-b down"):
        coro.send(None)
    loop.close()


def test_quiz_call_soon_and_call_later_order():
    order = []

    async def main():
        loop = asyncio.get_running_loop()
        loop.call_later(0.05, order.append, "x")
        loop.call_soon(order.append, "y")
        loop.call_later(0.01, order.append, "z")
        await asyncio.sleep(0.1)

    asyncio.run(main())
    assert order == ["y", "z", "x"]


def test_quiz_set_exception_reaches_the_coroutine_and_is_stored_on_the_task():
    async def main():
        loop = asyncio.get_running_loop()
        fut = loop.create_future()

        async def seller_c():
            await fut

        task = asyncio.create_task(seller_c())
        await asyncio.sleep(0)
        fut.set_exception(SellerError("seller-c failed"))
        await asyncio.sleep(0.01)
        return task

    task = asyncio.run(main())
    assert isinstance(task.exception(), SellerError)


def test_quiz_two_faulty_sellers_toy_loop_fails_v3_answers():
    with pytest.raises(SellerError, match="seller-c"):
        quiet(gateway_v1.compare, "kettle-1l", budget_ms=BUDGET_MS, faulty={"seller-c", "seller-d"})

    async def main():
        with running_sellers(faulty={"seller-c", "seller-d"}) as ports:
            return await gateway_v3.compare(ports, "kettle-1l", budget_ms=BUDGET_MS)

    best, failed, missed, _ = quiet(asyncio.run, main())
    assert (best.seller, best.price) == ("seller-b", 1199)
    assert [n for n, _ in failed] == ["seller-c", "seller-d"] and missed == ["seller-e"]


def test_quiz_cancelled_seller_e_task_is_cancelled_and_connection_closed():
    async def main():
        with running_sellers() as ports:
            return await gateway_v3.compare(ports, "kettle-1l", budget_ms=BUDGET_MS)

    best, failed, missed, ms = quiet(asyncio.run, main())
    assert missed == ["seller-e"] and not failed and abs(ms - 250) <= 60


def test_level_triggered_selector_keeps_reporting_unread_data():
    a, b = socket.socketpair()
    with selectors.DefaultSelector() as sel, a, b:
        sel.register(a, selectors.EVENT_READ)
        b.sendall(b"seller-b 1199\n")
        assert len(sel.select(timeout=1)) == 1
        assert len(sel.select(timeout=1)) == 1  # not read yet: reported again
        a.recv(100)
        assert sel.select(timeout=0) == []


def test_predict_polling_task_forces_timeout_zero():
    import tracing

    timeouts = []

    class Recording(tracing.TracingSelector):
        printing = False

        def select(self, timeout=None):
            timeouts.append(timeout)
            return super().select(timeout)

    async def main():
        done = False

        async def flip():
            nonlocal done
            await asyncio.sleep(0.05)
            done = True

        flipper = asyncio.create_task(flip())
        while not done:
            await asyncio.sleep(0)
        await flipper

    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(Recording()))
    assert len(timeouts) > 100 and timeouts.count(0) > 0.9 * len(timeouts)


@pytest.mark.skipif(not LINUX, reason="fd numbering as on Linux")
def test_predict_fd_limit_32():
    code = textwrap.dedent(
        """
        import errno, resource, socket
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, hard))
        socks = []
        try:
            while True:
                socks.append(socket.socket())
        except OSError as e:
            print(socks[-1].fileno(), errno.errorcode[e.errno])
        """
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.split() == ["31", "EMFILE"]


def test_setrlimit_refuses_soft_above_hard():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if hard == resource.RLIM_INFINITY:
        pytest.skip("unlimited hard limit")
    with pytest.raises(ValueError):
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard + 1, hard))


def test_quiz_call_soon_from_thread_waits_for_next_timer():
    import cross_thread

    assert abs(cross_thread.trial("call_soon") - 1000) <= 60
    assert abs(cross_thread.trial("call_soon_threadsafe") - 100) <= 60


def test_sellers_are_the_series_numbers_on_the_wire():
    with running_sellers() as ports:
        for seller in SELLERS:
            with socket.create_connection(("127.0.0.1", ports[seller.name])) as sock:
                sock.sendall(b"x\n")
                assert sock.recv(100) == f"{seller.name} {seller.price}\n".encode()

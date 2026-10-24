"""Part 8: the page shows what the code does, and every check's answer holds."""

import asyncio
import contextlib
import gc
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-8"
BODY = (CONTENT / "body.html").read_text()
LINUX = sys.platform.startswith("linux")


def run_script(tmp_path, code, timeout=60):
    """Run `code` as a script file whose imports resolve to this folder (pool workers need a real file)."""
    script = tmp_path / "case.py"
    script.write_text(f"import sys\nsys.path.insert(0, {str(HERE)!r})\n{code}")
    done = subprocess.run(
        [sys.executable, str(script)], cwd=HERE, capture_output=True, text=True, timeout=timeout
    )
    return done.stdout, done.stderr


# ---- the series plan and the links ---------------------------------------------


def test_meta_keeps_the_series_plan_and_links_all_eight_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert [p["slug"] for p in meta["prereqs"]] == [f"python-asyncio-{n}" for n in range(1, 8)]
    for n in range(1, 8):
        other = json.loads((CONTENT.parent / f"python-asyncio-{n}" / "meta.json").read_text())["related"]
        assert other[7].get("slug") == "python-asyncio-8"
    page7 = (CONTENT.parent / "python-asyncio-7" / "body.html").read_text()
    assert '<a href="../python-asyncio-8/index.html">Part 8' in page7
    assert '<a href="../python-asyncio-9/index.html">Part 9' in BODY  # the link to the next page


def test_every_example_program_with_output_is_on_the_page():
    for out in (HERE / "out").glob("*.txt"):
        if f'data-file="{out.stem}.py"' in BODY:
            assert f'data-file="out/{out.stem}.txt"' in BODY, out.stem


# ---- rung 1 ------------------------------------------------------------------------


@pytest.mark.skipif(not LINUX, reason="signals and process groups as on Linux")
def test_predict_sigterm_between_requests_still_ends_v8_with_minus_15(capsys):
    from deploy import deploy

    deploy("server_v8.py", sigterm_at=0.4, late_at=0.45)
    out = capsys.readouterr().out
    assert "20 shoppers: {'seller-b 1199': 20}" in out
    assert "refused (ConnectionRefusedError)" in out
    assert "return code -15" in out


# ---- rung 2 ------------------------------------------------------------------------


@pytest.mark.skipif(not LINUX, reason="POSIX signals")
def test_quiz_signal_signal_is_seen_at_the_next_timer_wake_up(tmp_path):
    code = """
import asyncio, signal, os, threading
async def main():
    loop = asyncio.get_running_loop()
    start = loop.time()
    stop = asyncio.Event()
    signal.signal(signal.SIGTERM, lambda s, f: stop.set())
    async def health():
        while True:
            await asyncio.sleep(0.3)  # the health check's timer, scaled from 5 s
    task = asyncio.create_task(health())
    threading.Timer(0.05, os.kill, (os.getpid(), signal.SIGTERM)).start()
    await stop.wait()
    print(round((loop.time() - start) * 1000))
    task.cancel()
asyncio.run(main())
"""
    out, err = run_script(tmp_path, code, timeout=10)
    assert err == ""
    assert 250 <= int(out) <= 400  # sent at 50 ms, seen when the 300 ms timer woke the loop


def test_predict_cancel_while_the_generator_waits_runs_its_finally_in_the_request():
    from offer_stream import offers

    async def main():
        seen = []

        async def ask(name, port):
            await asyncio.sleep({"a": 0.01, "b": 1.0}[name])
            return name

        async def gen_with_mark():
            try:
                async for offer in offers(ask, {"a": None, "b": None}, "kettle-1l"):
                    yield offer
            finally:
                seen.append(("generator finally", asyncio.current_task().get_name()))

        async def request():
            stream = gen_with_mark()
            try:
                async for _ in stream:
                    pass  # waits for "b" inside the generator
            finally:
                seen.append(("request finally", asyncio.current_task().get_name()))

        task = asyncio.create_task(request(), name="request")
        await asyncio.sleep(0.05)
        task.cancel()  # the hang-up watch
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return seen

    assert asyncio.run(main()) == [("generator finally", "request"), ("request finally", "request")]


def test_quiz_yield_in_finally_makes_aclose_raise_runtime_error():
    async def gen():
        try:
            yield 1
            yield 2
        finally:
            yield "closing"

    async def main():
        with pytest.raises(RuntimeError):
            async with contextlib.aclosing(gen()) as g:
                async for _ in g:
                    break

    asyncio.run(main())


def test_quiz_exit_stack_closes_only_what_was_entered(capsys):
    import exit_stack  # runs the page's two cases on import

    capsys.readouterr()
    with pytest.raises(OSError):
        asyncio.run(exit_stack.start(fail_at="seller-e feed"))
    lines = [line.strip() for line in capsys.readouterr().out.splitlines()]
    assert lines == [
        "open  audit writers",
        "open  metrics flusher",
        "close metrics flusher",
        "close audit writers",
    ]


# ---- rung 3 ------------------------------------------------------------------------


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_quiz_a_drain_deadline_that_covers_the_audit_queue_answers_all_ten(tmp_path):
    code = """
import gateway_v9, drain_deadline
Original = gateway_v9.Budget
gateway_v9.Budget = lambda **kw: Original(**{**kw, "drain": 1.5})
if __name__ == "__main__":
    drain_deadline.main()
"""
    out, err = run_script(tmp_path, code)
    assert err == ""
    assert "10 shoppers: {'seller-b 1199': 10}" in out
    assert "drained: no request left in flight" in out
    assert "audit rows written: {'seller-b at 1,199': 10}; lost: 0" in out


@pytest.mark.skipif(not LINUX, reason="signals and process groups as on Linux")
def test_predict_a_hanging_seller_e_fill_is_cancelled_and_the_process_still_exits(tmp_path, capsys):
    from deploy import deploy

    script = tmp_path / "hang_v9.py"
    script.write_text(
        f"import dataclasses, sys\nsys.path.insert(0, {str(HERE)!r})\n"
        "import sellers, sellers_net\n"
        "sellers_net.SELLERS = tuple(dataclasses.replace(s, latency_ms=30000) if s.name == 'seller-e' else s"
        " for s in sellers.SELLERS)\n"
        "import gateway_v9\n"
        "if __name__ == '__main__':\n    gateway_v9.main()\n"
    )
    deploy(str(script))
    out = capsys.readouterr().out
    assert "fills: 0 finished, 1 cancelled" in out
    assert "process: exit 0" in out
    assert "process exited by itself; return code 0; stderr lines: 0" in out


def test_quiz_executor_shutdown_waits_for_a_running_call():
    from concurrent.futures import ThreadPoolExecutor

    release = threading.Event()
    pool = ThreadPoolExecutor(max_workers=1)
    pool.submit(release.wait)
    threading.Timer(0.2, release.set).start()
    t0 = time.monotonic()
    pool.shutdown(wait=True, cancel_futures=True)  # the running call is not cancelled
    assert time.monotonic() - t0 >= 0.15


# ---- rung 4 ------------------------------------------------------------------------


def test_quiz_call_soon_threadsafe_on_a_closed_loop_raises():
    loop = asyncio.new_event_loop()
    loop.close()
    with pytest.raises(RuntimeError):
        loop.call_soon_threadsafe(lambda: None)


def test_predict_closing_loop_one_first_runs_the_finally_during_its_close(capsys):
    import wrong_loop  # runs the page's two cases on import

    capsys.readouterr()
    kept = []

    async def first_iteration():
        kept.append(wrong_loop.prices("gen 3"))
        await anext(kept[0])

    loop_one = asyncio.Runner()
    wrong_loop.loops[loop_one.get_loop()] = "loop 1"
    loop_one.run(first_iteration())
    print("closing loop 1")
    loop_one.close()
    print("loop 1 closed")

    async def drop_it():
        kept.clear()
        gc.collect()
        await asyncio.sleep(0.01)

    with asyncio.Runner() as loop_two:
        wrong_loop.loops[loop_two.get_loop()] = "loop 2"
        loop_two.run(drop_it())
    lines = [line.strip() for line in capsys.readouterr().out.splitlines()]
    assert lines == [
        "closing loop 1",
        "gen 3: finally starts, on loop 1",
        "gen 3: finally done",
        "loop 1 closed",
    ]


@pytest.mark.skipif(not LINUX, reason="POSIX signals")
def test_forwarding_a_signal_from_the_main_thread_stops_a_loop_in_another_thread():
    stopped = threading.Event()
    ready = threading.Event()
    box = {}

    def loop_thread():
        async def main():
            box["loop"], box["stop"] = asyncio.get_running_loop(), asyncio.Event()
            ready.set()
            await box["stop"].wait()
            stopped.set()

        asyncio.run(main())

    worker = threading.Thread(target=loop_thread)
    worker.start()
    ready.wait(1)

    def forward(signum, frame):
        box["loop"].call_soon_threadsafe(box["stop"].set)

    previous = signal.signal(signal.SIGUSR1, forward)
    try:
        os.kill(os.getpid(), signal.SIGUSR1)
        assert stopped.wait(1.0)
    finally:
        signal.signal(signal.SIGUSR1, previous)
        worker.join(1)


def test_quiz_halving_the_batch_numbers():
    total = 80 * 2_000
    assert round(total / 60) == 2_667 and round(total / 70) == 2_286
    assert 20 * 5 * 1_000 == 100_000 and 10 * 5 * 1_000 == 50_000
    assert 2_000 * 2 * 20 * (80 // 20) == 320_000  # refusals over a rollout do not depend on the batch
    assert 2_000 * 2 * 10 * (80 // 10) == 320_000


# ---- rung 5 ------------------------------------------------------------------------


def test_quiz_ack_on_take_leaves_jobs_charged_but_not_recorded(capsys, monkeypatch):
    import stop_ways  # runs the page's five cases on import

    capsys.readouterr()

    class AckOnTake(stop_ways.Broker):
        def take(self):
            return self.ready.pop(0) if self.ready else None  # acknowledged at once: never in `taken`

    monkeypatch.setattr(stop_ways, "Broker", AckOnTake)
    line = asyncio.run(stop_ways.run("hard stop", True, False))
    assert line.endswith("never charged [], charged twice [], charged but not recorded [3, 4]")


def test_quiz_a_hang_up_during_the_drain_is_labelled_stopped_by_shutdown():
    import gateway_v9

    gw = object.__new__(gateway_v9.Gateway)
    gw.draining, gw.stopped_by_shutdown, gw.hung_up, rows = True, 0, 0, []

    async def compare(item):
        await asyncio.sleep(1)

    async def audit(row):
        rows.append(row)

    gw.compare, gw._audit = compare, audit

    async def main():
        task = asyncio.create_task(gw.handle("sale-1", "kettle-1l", asyncio.get_running_loop().time()))
        await asyncio.sleep(0.01)
        task.cancel()  # the hang-up watch's cancel, with no message
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(main())
    assert gw.stopped_by_shutdown == 1 and gw.hung_up == 0
    assert "stopped by shutdown" in rows[0]


def test_order_gateway_versions_are_numbered_in_build_order():
    names = sorted(HERE.glob("gateway_v*.py"), key=lambda p: int(p.stem.removeprefix("gateway_v")))
    assert [p.stem for p in names] == [f"gateway_v{n}" for n in range(10)]

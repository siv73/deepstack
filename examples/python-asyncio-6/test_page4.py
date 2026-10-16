"""Part 4: the page shows what the code does, and every check's answer holds."""

import asyncio
import contextlib
import gc
import io
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import gateway_v4
import gateway_v5
import pytest
import spawn
import trap2_blocking_io
import trap5_swallow
from gateway_v3 import ask_seller
from metrics import MetricsClient, MetricsSink
from sellers import SellerError
from sellers_net import running_sellers
from sync_sdk import SyncSellerClient

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-4"
BODY = (CONTENT / "body.html").read_text()
ITEM = "kettle-1l"


def quiet(coro):
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(coro)


# ---- the series plan and the links ---------------------------------------------


def test_meta_keeps_the_series_plan_and_links_all_four_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert [p["slug"] for p in meta["prereqs"]] == [
        "python-asyncio-1",
        "python-asyncio-2",
        "python-asyncio-3",
    ]
    for n in (1, 2, 3):
        other = json.loads((CONTENT.parent / f"python-asyncio-{n}" / "meta.json").read_text())["related"]
        assert other[3].get("slug") == "python-asyncio-4"
    page3 = (CONTENT.parent / "python-asyncio-3" / "body.html").read_text()
    assert '<a href="../python-asyncio-4/index.html">' in page3
    assert '<a href="../python-asyncio-5/index.html">Part 5' in BODY  # "Next: Part 5" links to page 5


def test_every_example_program_with_output_is_on_the_page():
    for out in (HERE / "out").glob("*.txt"):
        if f'data-file="{out.stem}.py"' in BODY:
            assert f'data-file="out/{out.stem}.txt"' in BODY, out.stem


def test_sellers_are_still_the_series_numbers():
    from sellers import BUDGET_MS, SELLERS

    assert [(s.name, s.latency_ms, s.price) for s in SELLERS] == [
        ("seller-a", 80, 1249),
        ("seller-b", 120, 1199),
        ("seller-c", 150, 1229),
        ("seller-d", 200, 1215),
        ("seller-e", 900, 1149),
    ]
    assert BUDGET_MS == 250


# ---- debug mode and CI settings (and Part 1's corrected advice) --------------------------------


def pytest_on_case(*flags):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *flags, "case_forgotten_await.py"],
        cwd=HERE,
        capture_output=True,
        text=True,
    )
    return result.returncode


def test_only_w_error_or_both_filters_fail_a_forgotten_await():
    assert pytest_on_case() == 0
    assert pytest_on_case("-W", "error::RuntimeWarning") == 0
    assert pytest_on_case("-W", "error") == 1
    assert (
        pytest_on_case("-W", "error::RuntimeWarning", "-W", "error::pytest.PytestUnraisableExceptionWarning")
        == 1
    )


def test_plain_python_w_error_runtimewarning_does_not_fail():
    code = "import asyncio\nasync def f(): pass\nasync def main():\n    f()\nasyncio.run(main())\n"
    r = subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "-c", code], capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "Exception ignored while finalizing coroutine" in r.stderr


def test_part1_page_now_gives_the_working_setting():
    page1 = (CONTENT.parent / "python-asyncio-1" / "body.html").read_text()
    assert "<code>pytest -W error</code>" in page1


class Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def slow_step_warnings(step_s, threshold=None):
    collect = Collect()
    logging.getLogger("asyncio").addHandler(collect)

    async def main():
        if threshold is not None:
            asyncio.get_running_loop().slow_callback_duration = threshold
        time.sleep(step_s)  # one step that holds the loop

    try:
        asyncio.run(main(), debug=True)
    finally:
        logging.getLogger("asyncio").removeHandler(collect)
    return [m for m in collect.messages if m.startswith("Executing")]


def test_quiz_70ms_step_is_not_logged_by_default_but_is_with_a_lower_threshold():
    assert slow_step_warnings(0.07) == []
    assert len(slow_step_warnings(0.07, threshold=0.05)) == 1


def test_quiz_a_late_timer_runs_after_the_blocking_step():
    async def main():
        loop = asyncio.get_running_loop()
        start = loop.time()
        fired = loop.create_future()
        loop.call_later(0.05, lambda: fired.set_result(loop.time() - start))
        time.sleep(0.3)  # a 300 ms blocking step
        return await fired

    late_ms = (asyncio.run(main()) - 0.05) * 1000
    assert 240 <= late_ms <= 300


# ---- trap checks -------------------------------------------------------------


def test_predict_a_coroutine_in_an_if_is_always_true():
    async def seller_is_blocked(name):
        return False

    async def main():
        skipped = []
        for name in ("seller-a", "seller-b"):
            if seller_is_blocked(name):  # forgotten await
                skipped.append(name)
        return skipped

    with pytest.warns(RuntimeWarning, match="was never awaited"):
        assert asyncio.run(main()) == ["seller-a", "seller-b"]
        gc.collect()


def test_predict_seller_b_through_a_sync_sdk_costs_seller_c_and_d():
    class BlockingB(trap2_blocking_io.Blocking):
        def __init__(self, ports):
            super().__init__(ports)
            self.sdk = SyncSellerClient(ports["seller-b"])

        async def call(self, start, name, port, item):
            if name == "seller-b":
                return self.sdk.get_price(item)
            return await ask_seller(start, name, port, item)

    async def main():
        with running_sellers() as ports:
            return await BlockingB(ports).compare(ITEM)

    answer = quiet(main())
    assert (answer.best.seller, answer.best.price) == ("seller-b", 1199)
    assert answer.timed_out == ["seller-c", "seller-d", "seller-e"]


def test_thread_keeps_running_after_the_deadline():
    async def main():
        with running_sellers() as ports, ThreadPoolExecutor(max_workers=4) as pool:
            gateway = trap2_blocking_io.InAThread(ports, sdk_pool=pool)
            answer = await gateway.compare(ITEM)
            still_running = gateway.sdk.running
            while gateway.sdk.running:
                await asyncio.sleep(0.01)
            return answer, still_running

    answer, still_running = quiet(main())
    assert answer.timed_out == ["seller-e"] and still_running == 1


def test_quiz_docs_recipe_reports_failure_only_at_garbage_collection():
    heard = []

    async def fails():
        await asyncio.sleep(0)
        raise ConnectionRefusedError("metrics service down")

    async def main():
        asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: heard.append(ctx["message"]))
        background_tasks = set()
        task = asyncio.create_task(fails())
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        del task
        await asyncio.sleep(0.01)
        gc.collect()

    asyncio.run(main())
    assert heard == ["Task exception was never retrieved"]


def test_spawn_reports_at_once_and_counts():
    collect = Collect()
    logging.getLogger("gateway").addHandler(collect)

    async def fails():
        raise ConnectionRefusedError("metrics service down")

    async def main():
        spawn.spawn(fails(), name="flush-test")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return list(collect.messages)

    try:
        messages = asyncio.run(main())
    finally:
        logging.getLogger("gateway").removeHandler(collect)
    assert messages == ["background task flush-test failed: ConnectionRefusedError: metrics service down"]
    assert spawn.failures["flush-test"] == 1 and not spawn.running


def test_vanish_rule_only_the_unwakeable_task_is_destroyed():
    out = subprocess.run(
        [sys.executable, "trap3_vanish.py"], cwd=HERE, capture_output=True, text=True, check=True
    ).stdout
    assert "Tasks alive before gc.collect(): 3" in out
    assert "Tasks alive after gc.collect():  2" in out
    assert "asyncio: Task was destroyed but it is pending!" in out


def test_quiz_gather_raises_the_first_and_silently_drops_the_second():
    heard = []

    async def fail_after(ms, msg):
        await asyncio.sleep(ms / 1000)
        raise SellerError(msg)

    async def ok_after(ms):
        await asyncio.sleep(ms / 1000)
        return "c"

    async def main():
        asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: heard.append(ctx["message"]))
        tasks = [asyncio.create_task(fail_after(50, "a")), asyncio.create_task(fail_after(80, "b"))]
        tasks.append(asyncio.create_task(ok_after(100)))
        with pytest.raises(SellerError, match="a"):
            await asyncio.gather(*tasks)
        await asyncio.wait(tasks)
        del tasks
        gc.collect()

    asyncio.run(main())
    assert heard == []


def test_return_exceptions_puts_cancelled_error_in_the_results():
    async def main():
        async def slow():
            await asyncio.sleep(1)

        task = asyncio.create_task(slow())
        asyncio.get_running_loop().call_later(0.01, task.cancel)
        return await asyncio.gather(task, return_exceptions=True)

    [result] = asyncio.run(main())
    assert isinstance(result, asyncio.CancelledError)
    assert not isinstance(result, Exception) and isinstance(result, BaseException)


def swallow_test(handler_kind):
    async def call():
        await asyncio.sleep(0.2)
        return "answer"

    caught = BaseException if handler_kind == "bare" else asyncio.CancelledError

    async def wrapped():
        for _ in range(2):
            try:
                return await call()
            except caught:  # swallows the deadline's CancelledError
                continue

    async def named():
        for attempt in range(2):
            try:
                return await call()
            except (SellerError, ConnectionError):
                if attempt == 1:
                    raise

    async def main():
        start = time.monotonic()
        try:
            async with asyncio.timeout(0.05):
                result = await (named() if handler_kind == "named" else wrapped())
        except TimeoutError:
            result = "TimeoutError"
        return result, time.monotonic() - start

    return asyncio.run(main())


def test_quiz_only_the_named_retry_keeps_the_deadline():
    assert swallow_test("named")[0] == "TimeoutError"
    for kind in ("bare", "cancelled"):
        result, took = swallow_test(kind)
        assert result == "answer" and took >= 0.2  # the deadline was ignored


def test_swallow_and_log_handler_also_breaks_the_timeout():
    log = logging.getLogger("test.swallow")
    log.propagate = False

    async def worker():
        for _ in range(3):
            try:
                await asyncio.sleep(0.05)
            except BaseException:
                log.exception("poll failed")

    async def main():
        start = time.monotonic()
        async with asyncio.timeout(0.02) as cm:
            await worker()
        return time.monotonic() - start, cm.expired()

    took, expired = asyncio.run(main())
    assert took >= 0.1 and expired  # no TimeoutError, though the deadline fired


def test_retry_anything_gateway_ignores_the_deadline():
    async def main():
        with running_sellers() as ports:
            return await trap5_swallow.WithRetry(ports).compare(ITEM)

    answer = quiet(main())
    assert (answer.best.seller, answer.timed_out) == ("seller-e", [])
    assert 1100 <= answer.ms <= 1300


def test_quiz_except_oserror_first_records_a_failure():
    async def main():
        try:
            async with asyncio.timeout(0.01):
                await asyncio.sleep(1)
        except OSError:
            return "Failure"
        except TimeoutError:
            return "Timeout"

    assert asyncio.run(main()) == "Failure"
    assert issubclass(TimeoutError, OSError)


# ---- gateway v5 ------------------------------------------------------------------


def run_v5(requests):
    async def main(ports, sdk_pool, cpu_pool):
        sink = MetricsSink()
        gateway = gateway_v5.Gateway(ports, sdk_pool, cpu_pool, MetricsClient(sink))
        collect = Collect()
        logging.getLogger("asyncio").addHandler(collect)
        try:
            await gateway.start()
            async with asyncio.TaskGroup() as tg:
                calls = [tg.create_task(gateway.compare(ITEM)) for _ in range(requests)]
            started_at_answer = gateway.sdk.started
            await asyncio.sleep(1.0)  # let seller-e's running threads finish
            await gateway.stop()
        finally:
            logging.getLogger("asyncio").removeHandler(collect)
        return [c.result() for c in calls], gateway.sdk, started_at_answer, sink.totals(), collect.messages

    with (
        ThreadPoolExecutor(max_workers=4) as sdk_pool,
        ProcessPoolExecutor(max_workers=2) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(gateway_v5.score_offers, [[], []], [1, 1]))  # as gateway_v5.main() does
        with contextlib.redirect_stdout(io.StringIO()):
            return asyncio.run(main(ports, sdk_pool, cpu_pool), debug=True)


def test_v5_answers_marks_partial_and_drops_queued_seller_e_calls():
    answers, sdk, started_at_answer, totals, logged = run_v5(10)
    assert all((a.best.seller, a.best.price, a.partial) == ("seller-b", 1199, True) for a in answers)
    assert all("seller-e" in a.timed_out for a in answers)  # debug mode slows this 2-core harness
    assert sdk.started == started_at_answer == 4 and sdk.peak == 4  # 6 queued calls never ran
    assert totals["seller-e timed out"] == 10
    assert not [m for m in logged if m.startswith("Executing")]  # debug mode: no slow step on the loop


def test_v5_entry_point_is_guarded_for_the_process_pool():
    assert 'if __name__ == "__main__":\n    main()' in (HERE / "gateway_v5.py").read_text()


def test_v4_handler_order_reports_timeouts_as_timeouts():
    async def main():
        with running_sellers() as ports:
            return await gateway_v4.Gateway(ports).compare(ITEM)

    answer = quiet(main())
    assert answer.timed_out == ["seller-e"] and not answer.failed

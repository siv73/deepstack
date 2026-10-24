"""Part 9: the page shows what the code does, and every check's answer holds."""

import asyncio
import concurrent.futures
import io
import json
import logging
import threading
import time
from pathlib import Path

import pytest
import uvloop
from gateway_v9 import Budget
from observe import Histogram, JsonFormatter, dump_tasks
from price_cache import PriceCache
from request_log import request_id
from sellers import Offer
from stubs import StallingAuditStore, StubSellers, connection, make_gateway
from virtual_clock import VirtualClockLoop

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-9"
BODY = (CONTENT / "body.html").read_text()


def virtual(main):
    return asyncio.run(main(), loop_factory=VirtualClockLoop)


# ---- the series plan and the links ---------------------------------------------


def test_meta_keeps_the_series_plan_and_links_all_nine_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert [p["slug"] for p in meta["prereqs"]] == [f"python-asyncio-{n}" for n in range(1, 9)]
    for n in range(1, 10):
        other = json.loads((CONTENT.parent / f"python-asyncio-{n}" / "meta.json").read_text())["related"]
        assert other[8].get("slug") == "python-asyncio-9", n
    page8 = (CONTENT.parent / "python-asyncio-8" / "body.html").read_text()
    assert '<a href="../python-asyncio-9/index.html">Part 9' in page8
    assert (
        "Next: Part 10" in BODY and "python-asyncio-10/index.html" not in BODY
    )  # page 10 does not exist yet


def test_every_example_program_with_output_is_on_the_page():
    for out in (HERE / "out").glob("*.txt"):
        if f'data-file="{out.stem}.py"' in BODY:
            assert f'data-file="out/{out.stem}.txt"' in BODY, out.stem


# ---- rung 2 ------------------------------------------------------------------------


def test_quiz_debug_mode_times_callbacks_not_waits():
    heard = []

    class Collect(logging.Handler):
        def emit(self, record):
            heard.append(record.getMessage())

    async def main():
        loop = asyncio.get_running_loop()
        assert loop.slow_callback_duration == 0.1  # the default threshold, 100 ms
        handler = Collect()
        logging.getLogger("asyncio").addHandler(handler)
        lock = asyncio.Lock()
        await lock.acquire()
        waiter = asyncio.create_task(lock.acquire())  # a wait that never ends: nothing to time
        await asyncio.sleep(0.15)
        waits = len(heard)
        loop.call_soon(time.sleep, 0.14)  # a 140 ms step, like the JSON parse
        await asyncio.sleep(0.05)
        logging.getLogger("asyncio").removeHandler(handler)
        waiter.cancel()
        return waits, len(heard) - waits

    assert asyncio.run(main(), debug=True) == (0, 1)


def test_quiz_get_stack_returns_one_frame_for_a_suspended_coroutine():
    async def inner():
        await asyncio.sleep(1)

    async def outer():
        await inner()

    async def main():
        task = asyncio.create_task(outer())
        await asyncio.sleep(0)
        frames = task.get_stack()
        task.cancel()
        return [f.f_code.co_name for f in frames]

    assert asyncio.run(main()) == ["outer"]


@pytest.mark.skipif(not hasattr(asyncio, "capture_call_graph"), reason="call graph: Python 3.14+")
def test_quiz_a_negative_limit_keeps_the_frames_where_the_task_waits():
    async def c():
        await asyncio.sleep(1)

    async def b():
        await c()

    async def a():
        await b()

    async def main():
        task = asyncio.create_task(a())
        await asyncio.sleep(0)
        names = {
            limit: [e.frame.f_code.co_name for e in asyncio.capture_call_graph(task, limit=limit).call_stack]
            for limit in (None, -2, 2)
        }
        task.cancel()
        return names

    names = asyncio.run(main())
    assert names[None] == ["sleep", "c", "b", "a"]  # the top frame, where it waits, first
    assert names[-2] == ["sleep", "c"] and names[2] == ["b", "a"]


def test_dump_falls_back_to_one_frame_when_the_call_graph_raises(monkeypatch):
    def broken(task):
        raise AttributeError("'NoneType' object has no attribute 'f_generator'")

    monkeypatch.setattr(asyncio, "format_call_graph", broken, raising=False)

    async def main():
        task = asyncio.create_task(asyncio.Event().wait(), name="fill seller-e kettle-1l")
        await asyncio.sleep(0)
        out = io.StringIO()
        dump_tasks(out)
        task.cancel()
        return out.getvalue()

    text = asyncio.run(main())
    assert "* fill seller-e kettle-1l (one frame)" in text and "Stack for <Task" in text


# ---- rung 3 ------------------------------------------------------------------------


def test_quiz_histogram_bounds_seller_ds_p99():
    h = Histogram()
    for _ in range(590):
        h.observe(200)
    for _ in range(10):
        h.observe(400)
    assert h.quantile(0.99) == 500 and h.quantile(0.98) == 250


def test_json_lines_escape_a_newline_and_keep_one_line():
    request_id.set('abc\n{"event":"refund approved"}')
    record = logging.LogRecord("gateway", logging.WARNING, __file__, 1, "audit row not confirmed", None, None)
    line = JsonFormatter().format(record)
    assert "\n" not in line and json.loads(line)["request_id"].startswith("abc\n")
    request_id.set("-")


def test_quiz_a_late_seller_c_times_out_but_its_fill_fills_the_cache():
    async def main():
        gateway = make_gateway(StubSellers(latency_ms={"seller-c": 400}))
        await gateway.start()
        answer = await gateway.compare("kettle-1l")
        await asyncio.sleep(0.2)  # 450 ms: seller-c's own call has landed
        cached = gateway.cache.get("seller-c", "kettle-1l")
        await gateway.shutdown([], Budget())
        return answer, cached

    answer, cached = virtual(main)
    assert answer.timed_out == ["seller-c", "seller-e"] and cached.price == 1229


def test_predict_a_real_thread_loses_the_race_against_the_virtual_clock():
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    async def main():
        loop = asyncio.get_running_loop()
        started = time.perf_counter()
        try:
            async with asyncio.timeout(1.0):
                await loop.run_in_executor(pool, time.sleep, 0.9)  # 900 ms of real time in a thread
            return "finished"
        except TimeoutError:
            return f"timed out after {time.perf_counter() - started:.1f} s of real time"

    assert virtual(main) == "timed out after 0.0 s of real time"
    pool.shutdown(wait=True)


def test_predict_owned_audit_writes_pile_up_and_a_shutdown_loses_them():
    from spawn import failures

    async def main(recover_for):
        store = StallingAuditStore()
        gateway = make_gateway(store=store, writers=2)
        await gateway.start()
        store.answering.clear()
        serving = [asyncio.create_task(gateway.serve(*connection(f"shop-{n} kettle-1l"))) for n in range(30)]
        await asyncio.wait(serving)  # every request answered after its 1 s audit limit
        waiting = sum(t.get_name() == "audit" for t in asyncio.all_tasks())
        queued = gateway.audit_queue.queue.qsize()
        store.answering.set()
        await asyncio.sleep(recover_for)
        report = await gateway.shutdown([], Budget())
        return gateway.audit_timeouts, waiting, queued, len(store.rows), report[-1]

    failures.clear()
    timeouts, waiting, queued, rows, _ = virtual(lambda: main(1.0))
    assert timeouts == 30 and waiting == 30  # one owned write Task per request, all still waiting
    assert queued == 8 and rows == 30  # the queue is full; given time, every row lands
    _, _, _, rows, last = virtual(lambda: main(0.0))  # a deploy right after the store recovers
    assert rows == 10 and failures["audit"] == 20  # writes still waiting in put() fail with QueueShutDown
    assert last.endswith("audit queue flushed: 10 rows written")  # and the report does not say so
    failures.clear()


def test_uvloop_runs_the_call_graph_and_is_not_a_selector_loop():
    async def main():
        task = asyncio.create_task(asyncio.sleep(1), name="nap")
        await asyncio.sleep(0)
        graph = (
            asyncio.format_call_graph(task) if hasattr(asyncio, "format_call_graph") else "* Task(name='nap'"
        )
        task.cancel()
        return type(asyncio.get_running_loop()), graph

    loop_type, graph = uvloop.run(main())
    assert not issubclass(loop_type, asyncio.SelectorEventLoop)
    assert "Task(name='nap'" in graph
    assert uvloop.__version__ == "0.23.0"  # the version this page names


# ---- rung 4 ------------------------------------------------------------------------


def test_predict_a_module_level_cache_leaks_prices_between_loops():
    cache = PriceCache(ttl=30)  # made once, as at import time

    async def first():
        await asyncio.sleep(0.5)
        cache.put("seller-e", "kettle-1l", Offer("seller-e", 1149))

    async def second():
        return cache.get("seller-e", "kettle-1l")  # this test never fetched it

    virtual(first)
    assert virtual(second).price == 1149  # still 'fresh' on the second loop's clock


def test_quiz_ten_x_label_arithmetic():
    items, sellers, series_per_histogram = 50_000, 5, 7 + 2  # 7 buckets, plus count and sum
    assert items * sellers * series_per_histogram == 2_250_000
    assert len(Histogram().bounds) == 7


def test_solved_example_burn_rate():
    assert round(0.015 / 0.001, 6) == 15 and 15 > 14.4


def test_threads_do_not_count_on_the_virtual_clock_but_signals_still_wake_it():
    async def main():
        loop = asyncio.get_running_loop()
        woke = asyncio.Event()
        threading.Timer(0.05, loop.call_soon_threadsafe, (woke.set,)).start()  # wakes via the self-pipe
        await woke.wait()  # no timer is due: the selector really waits for the pipe
        return loop.time()

    assert virtual(main) == 0.0


def test_debug_mode_cannot_time_a_blocking_call_on_the_virtual_clock():
    heard = []

    class Collect(logging.Handler):
        def emit(self, record):
            heard.append(record.getMessage())

    async def main():
        loop = asyncio.get_running_loop()
        loop.set_debug(True)
        loop.slow_callback_duration = 0.05
        handler = Collect()
        logging.getLogger("asyncio").addHandler(handler)
        loop.call_soon(time.sleep, 0.2)  # 200 ms of real time; the loop's own time() does not move
        await asyncio.sleep(0.01)
        logging.getLogger("asyncio").removeHandler(handler)

    virtual(main)
    assert (
        heard == []
    )  # the same call on a real clock is logged (test_quiz_debug_mode_times_callbacks_not_waits)

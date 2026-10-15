"""Part 5: the page shows what the code does, and every check's answer holds."""

import asyncio
import contextlib
import io
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import gateway_v6
from audit import AuditStore
from metrics import MetricsClient, MetricsSink
from scoring import score_offers
from sellers_net import running_sellers
from sync_sdk import SyncSellerClient

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-5"
BODY = (CONTENT / "body.html").read_text()


# ---- the series plan and the links ---------------------------------------------


def test_meta_keeps_the_series_plan_and_links_all_five_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert [p["slug"] for p in meta["prereqs"]] == [f"python-asyncio-{n}" for n in (1, 2, 3, 4)]
    for n in (1, 2, 3, 4):
        other = json.loads((CONTENT.parent / f"python-asyncio-{n}" / "meta.json").read_text())["related"]
        assert other[4].get("slug") == "python-asyncio-5"
    page4 = (CONTENT.parent / "python-asyncio-4" / "body.html").read_text()
    assert '<a href="../python-asyncio-5/index.html">' in page4
    assert "Next: Part 6" in BODY and "python-asyncio-6/index.html" not in BODY  # page 6 does not exist yet


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


# ---- rung 2 checks ------------------------------------------------------------------


def test_predict_right_after_cancel_the_task_is_neither_done_nor_cancelled():
    async def main():
        t = asyncio.create_task(asyncio.sleep(10))
        await asyncio.sleep(0)
        t.cancel()
        seen = (t.done(), t.cancelled())
        await asyncio.wait([t])
        return seen, t.cancelled()

    assert asyncio.run(main()) == ((False, False), True)


def test_solved_example_releasing_a_slot_by_hand_after_cancel_raises_the_cap_for_good():
    async def main():
        limit = asyncio.Semaphore(3)

        async def call():
            async with limit:
                await asyncio.sleep(10)

        task = asyncio.create_task(call())
        await asyncio.sleep(0)
        task.cancel()
        limit.release()  # the engineer's extra release
        await asyncio.wait([task])
        return limit._value  # inspected only in this test

    assert asyncio.run(main()) == 4


def test_predict_a_second_cancel_cuts_a_50_ms_cleanup_at_260_ms():
    log = []

    async def main():
        loop = asyncio.get_running_loop()
        start = loop.time()

        async def ask():
            try:
                await asyncio.sleep(0.9)
            finally:
                await asyncio.sleep(0.05)
                log.append("closed")

        task = asyncio.create_task(ask())
        loop.call_at(start + 0.25, task.cancel)
        loop.call_at(start + 0.26, task.cancel)
        await asyncio.wait([task])
        return round((loop.time() - start) * 100) * 10

    assert asyncio.run(main()) == 260
    assert log == []


def test_quiz_a_nested_inner_timeout_converts_only_its_own_cancel():
    async def main():
        loop = asyncio.get_running_loop()
        start = loop.time()
        async with asyncio.timeout(0.25):
            try:
                async with asyncio.timeout(0.1):
                    await asyncio.sleep(1)
            except TimeoutError:
                inner = round((loop.time() - start) * 100) * 10
            await asyncio.sleep(0.12)
        return inner, round((loop.time() - start) * 100) * 10

    assert asyncio.run(main()) == (100, 220)


# ---- rung 3 checks -------------------------------------------------------------------


def test_quiz_a_hang_up_records_no_seller_outcome_and_one_audit_row():
    async def serve(ports, sdk_pool, cpu_pool):
        sink, audit = MetricsSink(), AuditStore()
        gateway = gateway_v6.Gateway(
            ports, sdk_pool, cpu_pool, MetricsClient(sink, batch_size=1), audit=audit
        )
        server = await asyncio.start_server(gateway.serve, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            with contextlib.redirect_stdout(io.StringIO()):
                await gateway_v6.shopper(port, "shopper-2", "kettle-1l", hang_up_after=0.1)
                await asyncio.sleep(0.3)
        return sink.totals(), audit.rows, gateway.hung_up

    with (
        ThreadPoolExecutor(max_workers=4) as sdk_pool,
        ProcessPoolExecutor(max_workers=1) as cpu_pool,
        running_sellers() as ports,
    ):
        list(cpu_pool.map(score_offers, [[]], [1]))
        totals, rows, hung_up = asyncio.run(serve(ports, sdk_pool, cpu_pool))
    assert totals == {}  # no "timed out", no "failed": the request simply stopped
    assert len(rows) == 1 and "hung up after" in rows[0]
    assert hung_up == 1


def test_quiz_a_queued_executor_call_is_dropped_and_running_ones_continue():
    async def main(sdk, pool):
        loop = asyncio.get_running_loop()
        running = [loop.run_in_executor(pool, sdk.get_price, "kettle-1l", 0.2) for _ in range(4)]
        queued = loop.run_in_executor(pool, sdk.get_price, "kettle-1l", 0.2)
        await asyncio.sleep(0.05)
        queued.cancel()  # shopper-7 hangs up
        for f in running:
            f.cancel()
        await asyncio.sleep(0.3)
        return sdk.started

    with running_sellers() as ports, ThreadPoolExecutor(max_workers=4) as pool:
        sdk = SyncSellerClient(ports["seller-e"])
        assert asyncio.run(main(sdk, pool)) == 4  # the queued call never started


def test_shield_example_in_the_docs_wording_the_caller_is_cancelled_at_once():
    async def main():
        store = AuditStore(ms=40)
        task = asyncio.create_task(store.write("row"))

        async def handler():
            await asyncio.shield(task)

        holder = asyncio.create_task(handler())
        await asyncio.sleep(0.01)
        holder.cancel()
        await asyncio.wait([holder])
        at_10 = (holder.cancelled(), task.done())
        await task
        return at_10, store.rows

    assert asyncio.run(main()) == ((True, False), ["row"])


# ---- rung 4 checks -------------------------------------------------------------------


def test_quiz_wait_for_leaves_no_stale_count_so_a_later_failing_group_is_fine():
    async def slow():
        await asyncio.sleep(0.05)

    async def fails():
        raise ValueError("12x9")

    async def handler():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(slow(), 0.02)
        count = asyncio.current_task().cancelling()
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(fails())
                await asyncio.sleep(1)
        except* ValueError:
            pass
        await asyncio.sleep(0)  # the next await after the group
        return count, "502"

    assert asyncio.run(handler()) == (0, "502")


def test_quiz_314_a_hang_up_during_a_failing_groups_cleanup_reaches_the_next_await():
    import sys

    if sys.version_info < (3, 13):
        return  # the page measures the older behaviour with version_probe.py
    log = []

    async def bad():
        await asyncio.sleep(0.005)
        raise ValueError("12x9")

    async def slow():
        try:
            await asyncio.sleep(1)
        finally:
            await asyncio.sleep(0.02)

    async def handler():
        asyncio.get_running_loop().call_later(0.015, asyncio.current_task().cancel)
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(bad())
                tg.create_task(slow())
                await asyncio.sleep(1)
        except* ValueError:
            log.append("502")
        await asyncio.sleep(0.02)  # the audit write
        log.append("written")

    async def main():
        task = asyncio.create_task(handler())
        await asyncio.wait([task])
        return task.cancelled()

    assert asyncio.run(main()) is True
    assert log == ["502"]

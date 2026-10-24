"""Gateway v10's behaviour, tested on the virtual clock: exact times, no real waiting, the same every run."""

import asyncio
import time

import pytest
from gateway_v9 import Budget
from observe import json_lines
from spawn import failures
from stubs import StallingAuditStore, StubSellers, connection, hang_up, make_gateway
from virtual_clock import VirtualClockLoop


def run(main):
    """Run one test on a fresh virtual-clock loop, and fail it if it leaves any Task behind."""

    async def checked():
        result = await main()
        left = asyncio.all_tasks() - {asyncio.current_task()}
        assert not left, f"Tasks left running: {sorted(t.get_name() for t in left)}"
        return result

    return asyncio.run(checked(), loop_factory=VirtualClockLoop)


async def close(gateway):
    """Stop the way a deploy does (Part 8): gateway.stop() alone would leave seller-e's fill running."""
    return await gateway.shutdown([], Budget())


@pytest.fixture(autouse=True)
def no_background_failures():
    failures.clear()  # module-level state: reset it, or one test's failure shows up in the next
    yield
    assert not failures, dict(failures)


def test_the_budget_answers_seller_b_at_exactly_250_ms():
    async def main():
        gateway = make_gateway()
        await gateway.start()
        answer = await gateway.compare("kettle-1l")
        await close(gateway)
        return answer

    started = time.perf_counter()
    answer = run(main)
    assert (answer.best.seller, answer.best.price, answer.ms) == ("seller-b", 1199, 250)
    assert answer.timed_out == ["seller-e"] and answer.partial
    assert time.perf_counter() - started < 1.0  # 250 ms of gateway time, almost no real time


def test_a_seller_that_hangs_is_timed_out_and_its_call_ends_at_its_own_deadline():
    async def main():
        stubs = StubSellers()
        stubs.hanging.add("seller-c")
        gateway = make_gateway(stubs)
        await gateway.start()
        answer = await gateway.compare("kettle-1l")
        await asyncio.sleep(2.0)  # the fill's own deadline (Part 7: 2 s) ends the hanging call
        await close(gateway)
        return answer, gateway.seller_outcomes

    answer, outcomes = run(main)
    assert answer.timed_out == ["seller-c", "seller-e"] and answer.best.price == 1199
    assert outcomes["seller-c timed out"] == 1 and outcomes["seller-e answered"] == 1


def test_a_failing_seller_is_left_out_and_counted():
    async def main():
        stubs = StubSellers()
        stubs.failing.add("seller-b")
        gateway = make_gateway(stubs)
        await gateway.start()
        answer = await gateway.compare("kettle-1l")
        await close(gateway)
        return answer

    answer = run(main)
    assert (answer.best.seller, answer.best.price) == ("seller-d", 1215)
    assert [name for name, _ in answer.failed] == ["seller-b"]


def test_a_hang_up_cancels_the_request_but_not_the_shared_fill():
    async def main():
        gateway = make_gateway()
        await gateway.start()
        reader, writer = connection("shop-1 kettle-1l")
        loop = asyncio.get_running_loop()
        loop.call_later(0.1, hang_up, reader)  # the shopper leaves at 100 ms
        await gateway.serve(reader, writer)
        await asyncio.sleep(1.0)  # seller-e's fill (900 ms) was never the request's to cancel
        cached = gateway.cache.get("seller-e", "kettle-1l")
        await close(gateway)
        return writer.sent, gateway.audit_queue.store.rows, cached

    sent, rows, cached = run(main)
    assert sent == [] and rows == ["shop-1 kettle-1l: hung up after 100 ms"]
    assert cached.price == 1149


def test_shutdown_drains_then_waits_for_fills_in_order_with_exact_times():
    async def main():
        gateway = make_gateway()
        await gateway.start()
        serving = [asyncio.create_task(gateway.serve(*connection(f"shop-{n} grill-9"))) for n in (1, 2, 3)]
        await asyncio.sleep(0.1)  # SIGTERM arrives at 100 ms
        report = await gateway.shutdown([], Budget())
        await asyncio.wait(serving)
        return report, gateway.audit_queue.store.rows

    report, rows = run(main)
    assert report == [
        "    0 ms  listeners closed; 3 requests in flight",
        "  170 ms  drained: no request left in flight",
        "  800 ms  fills: 1 finished, 0 cancelled",
        "  800 ms  audit queue flushed: 3 rows written",
    ]
    assert sorted(rows) == [f"shop-{n} grill-9: seller-b at 1,199 after 250 ms" for n in (1, 2, 3)]


def test_a_drain_deadline_cancels_the_rest_and_labels_them():
    async def main():
        gateway = make_gateway()
        await gateway.start()
        serving = [asyncio.create_task(gateway.serve(*connection(f"shop-{n} grill-9"))) for n in (1, 2)]
        await asyncio.sleep(0.1)
        report = await gateway.shutdown([], Budget(drain=0.05, fills=0.1))
        await asyncio.wait(serving)
        return report, gateway.audit_queue.store.rows, gateway.request_outcomes

    report, rows, outcomes = run(main)
    assert report[1:4] == [
        "   50 ms  drain deadline: 2 requests still running",
        "   70 ms  cancelled 2 requests; 0 still unwinding",
        "  170 ms  fills: 1 finished, 1 cancelled",  # seller-d lands at 200 ms; seller-e (900 ms) does not
    ]
    assert sorted(rows) == [f"shop-{n} grill-9: stopped by shutdown after 150 ms" for n in (1, 2)]
    assert outcomes == {"stopped by shutdown": 2}


def test_a_stalled_audit_store_costs_one_second_and_is_counted_and_logged():
    async def main():
        lines = json_lines("gateway")
        store = StallingAuditStore()
        gateway = make_gateway(store=store)
        await gateway.start()
        store.answering.clear()  # the store stops answering
        await gateway.serve(*connection("shop-1 kettle-1l"))
        store.answering.set()  # and recovers, so shutdown can flush the row
        await close(gateway)
        return gateway, lines.events()

    gateway, events = run(main)
    assert gateway.audit_timeouts == 1 and gateway.request_ms.sum == 1250  # 250 ms, then 1 s for the row
    warning = next(e for e in events if e["event"] == "audit row not confirmed")
    assert (warning["request_id"], warning["level"], warning["at_ms"]) == ("shop-1", "WARNING", 1250)
    assert gateway.audit_queue.store.rows == [
        "shop-1 kettle-1l: seller-b at 1,199 after 250 ms"
    ]  # late, not lost


def test_loop_lag_sees_a_step_that_takes_300_ms():
    async def main():
        gateway = make_gateway()
        await gateway.start()
        loop = asyncio.get_running_loop()
        loop.call_at(0.06, loop.advance, 0.3)  # a callback at 60 ms that 'takes' 300 ms
        await asyncio.sleep(0.5)
        worst = gateway.lag.take_worst()
        await close(gateway)
        return worst

    assert run(main) == pytest.approx(260)  # the 100 ms sample fired at 360 ms

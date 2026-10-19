"""Part 7: the page shows what the code does, and every check's answer holds."""

import asyncio
import concurrent.futures
import contextvars
import json
import threading
from pathlib import Path

import pytest
from sellers import Offer
from single_flight import SingleFlight
from spawn import spawn

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-7"
BODY = (CONTENT / "body.html").read_text()


# ---- the series plan and the links ---------------------------------------------


def test_meta_keeps_the_series_plan_and_links_all_seven_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert [p["slug"] for p in meta["prereqs"]] == [f"python-asyncio-{n}" for n in range(1, 7)]
    for n in range(1, 7):
        other = json.loads((CONTENT.parent / f"python-asyncio-{n}" / "meta.json").read_text())["related"]
        assert other[6].get("slug") == "python-asyncio-7"
    page6 = (CONTENT.parent / "python-asyncio-6" / "body.html").read_text()
    assert '<a href="../python-asyncio-7/index.html">Part 7' in page6
    assert "Next: Part 8" in BODY and "python-asyncio-8/index.html" not in BODY  # page 8 does not exist yet


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


# ---- rung 1 ------------------------------------------------------------------------


def test_predict_await_before_the_read_loses_nothing():
    class Counter:
        calls = 0

        async def record(self):
            await asyncio.sleep(0.001)
            self.calls = self.calls + 1  # read and write with no await in between

    async def main():
        c = Counter()
        async with asyncio.TaskGroup() as tg:
            for _ in range(10):
                tg.create_task(c.record())
        return c.calls

    assert asyncio.run(main()) == 10


# ---- rung 2 ------------------------------------------------------------------------


def test_quiz_only_the_read_await_write_hit_loses_updates():
    class Store:
        def __init__(self):
            self.data = {"hits": 0}

        async def get(self, k):
            await asyncio.sleep(0)
            return self.data[k]

        async def set(self, k, v):
            await asyncio.sleep(0)
            self.data[k] = v

    async def main():
        store = Store()

        async def hit():
            n = await store.get("hits")
            await store.set("hits", n + 1)

        async with asyncio.TaskGroup() as tg:
            for _ in range(100):
                tg.create_task(hit())
        return store.data["hits"]

    assert asyncio.run(main()) < 100


def test_order_lock_waiters_go_first_in_first_out():
    async def main():
        lock, log = asyncio.Lock(), []

        async def user(name):
            async with lock:
                log.append(name)
                await asyncio.sleep(0.01)

        async with asyncio.TaskGroup() as tg:
            for name in ("t1", "t2", "t3"):
                tg.create_task(user(name))
        return log

    assert asyncio.run(main()) == ["t1", "t2", "t3"]


def test_quiz_wait_on_a_set_event_returns_at_once():
    async def main():
        event = asyncio.Event()
        event.set()
        task = asyncio.create_task(event.wait())
        await asyncio.sleep(0)  # one step is enough: it never parks
        return task.done() and task.result()

    assert asyncio.run(main()) is True


def test_event_set_then_clear_still_wakes_parked_waiters():
    async def main():
        event = asyncio.Event()
        waiter = asyncio.create_task(event.wait())
        await asyncio.sleep(0)
        event.set()
        event.clear()
        return await asyncio.wait_for(waiter, 0.1)

    assert asyncio.run(main()) is True


def test_predict_two_quorums_answer_at_120_and_200_ms():
    import condition_demo as cd
    from sellers import SELLERS

    async def main():
        cd.start = asyncio.get_running_loop().time()
        offers, cond, times = [], asyncio.Condition(), {}

        async def quorum(needed):
            async with cond:
                await cond.wait_for(lambda: len(offers) >= needed)
                times[needed] = cd.ms()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(quorum(2))
            tg.create_task(quorum(4))
            for s in SELLERS[:4]:
                tg.create_task(cd.seller(s, offers, cond))
        return times

    assert asyncio.run(main()) == {2: 120, 4: 200}


def test_quiz_cancelled_barrier_waiter_leaves_and_the_next_two_complete_it():
    async def main():
        barrier = asyncio.Barrier(3)
        first = asyncio.create_task(barrier.wait())
        second = asyncio.create_task(barrier.wait())
        await asyncio.sleep(0)
        first.cancel()
        await asyncio.sleep(0)
        assert barrier.n_waiting == 1
        third = asyncio.create_task(barrier.wait())
        fourth = asyncio.create_task(barrier.wait())
        positions = await asyncio.wait_for(asyncio.gather(second, third, fourth), 0.5)
        return sorted(positions), barrier.broken

    assert asyncio.run(main()) == ([1, 1, 2], False)  # all three pass; positions repeat after a cancel


def test_quiz_copy_context_before_the_set_prints_the_default():
    v = contextvars.ContextVar("v", default=0)

    def body():
        ctx = contextvars.copy_context()
        v.set(5)
        return ctx.run(v.get)

    assert contextvars.Context().run(body) == 0


# ---- rung 3 ------------------------------------------------------------------------


def test_quiz_without_shield_the_deadline_cancels_the_shared_fill():
    async def main():
        flights, stored = SingleFlight(), []

        async def fill():
            await asyncio.sleep(0.9)
            stored.append(Offer("seller-e", 1149))

        async def request():
            task = flights.start("kettle-1l", fill, name="fill seller-e kettle-1l")
            try:
                async with asyncio.timeout(0.25):
                    await task  # no shield
            except TimeoutError:
                pass
            return task

        tasks = await asyncio.gather(*(request() for _ in range(100)))
        await asyncio.sleep(0)
        return flights.started, tasks[0].cancelled(), stored

    assert asyncio.run(main()) == (1, True, [])


def test_quiz_shield_keeps_the_fill_running_after_the_timeout():
    async def main():
        flights, stored = SingleFlight(), []

        async def fill():
            await asyncio.sleep(0.3)
            stored.append(1149)

        task = flights.start("kettle-1l", fill, name="fill")
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                await asyncio.shield(task)
        await task
        return stored

    assert asyncio.run(main()) == [1149]


def test_quiz_spawn_before_the_set_sees_the_default_id():
    from request_log import request_id

    async def main():
        seen = []

        async def audit():
            seen.append(request_id.get())

        task = spawn(audit(), name="audit")
        request_id.set("shopper-1")
        await task
        return seen

    assert contextvars.Context().run(asyncio.run, main()) == ["-"]


def test_quiz_run_coroutine_threadsafe_returns_the_coroutine_result_to_the_thread():
    async def main():
        loop = asyncio.get_running_loop()

        async def apply_change():
            await asyncio.sleep(0.01)
            return "applied"

        def feed():
            return asyncio.run_coroutine_threadsafe(apply_change(), loop).result(timeout=1.0)

        return await asyncio.to_thread(feed)

    assert asyncio.run(main()) == "applied"


def test_waiting_on_the_concurrent_future_from_the_loop_thread_blocks_the_loop():
    async def main():
        loop = asyncio.get_running_loop()

        async def quick():
            return 1

        fut = asyncio.run_coroutine_threadsafe(quick(), loop)
        with pytest.raises(concurrent.futures.TimeoutError):
            fut.result(timeout=0.2)  # the loop cannot run quick() while we block it
        return await asyncio.wrap_future(fut)

    assert asyncio.run(main()) == 1


def test_predict_failed_seller_c_fill_is_shared_and_not_cached():
    from price_cache import PriceCache

    async def main():
        flights, cache, calls = SingleFlight(), PriceCache(ttl=30), []

        async def fill():
            calls.append(1)
            await asyncio.sleep(0.15)
            return "ERROR"  # returned, not stored

        async def request():
            offer = cache.get("seller-c", "kettle-1l")
            if offer is None:
                offer = await asyncio.shield(flights.start("kettle-1l", fill, name="fill"))
            return offer

        first = await asyncio.gather(*(request() for _ in range(100)))
        later = await asyncio.gather(*(request() for _ in range(10)))
        return set(first), len(calls), set(later)

    assert asyncio.run(main()) == ({"ERROR"}, 2, {"ERROR"})


# ---- rung 4 ------------------------------------------------------------------------


def test_predict_one_lock_three_misses_hold_up_a_cached_item_2700_ms():
    import lock_across_await as la

    async def main():
        la.start = asyncio.get_running_loop().time()
        cache, answered = la.OneLock(), {}
        cache.cache.put("seller-e", "kettle-1l", Offer("seller-e", 1149))

        async def ask(item, at_ms):
            await asyncio.sleep(at_ms / 1000)
            await cache.price(item)
            answered[item] = la.ms()

        async with asyncio.TaskGroup() as tg:
            for n, item in enumerate(("new-1", "new-2", "new-3")):
                tg.create_task(ask(item, n * 10))
            tg.create_task(ask("kettle-1l", 30))
        return answered["kettle-1l"]

    assert 2_650 <= asyncio.run(main()) <= 2_800


def test_quiz_same_lock_order_removes_the_deadlock():
    import deadlock

    async def main():
        deadlock.cache_lock, deadlock.quota_lock = asyncio.Lock(), asyncio.Lock()
        log = []
        await asyncio.wait_for(
            asyncio.gather(
                deadlock.refill(deadlock.cache_lock, deadlock.quota_lock, log),
                deadlock.report(deadlock.cache_lock, deadlock.quota_lock, log),
            ),
            1.0,
        )
        return sorted(log)

    assert asyncio.run(main()) == ["refill done", "report done"]


def test_quiz_done_callback_runs_in_the_adders_context():
    from request_log import request_id

    async def main():
        seen = []

        async def fill():
            request_id.set("fill seller-e toaster-2s")
            await asyncio.sleep(0.01)

        task = spawn(fill(), name="fill", context=contextvars.Context())
        request_id.set("shopper-4")
        task.add_done_callback(lambda _: seen.append(request_id.get()))
        await task
        await asyncio.sleep(0)
        return seen

    assert contextvars.Context().run(asyncio.run, main()) == ["shopper-4"]


def test_quiz_set_result_from_a_thread_wakes_only_when_the_loop_next_wakes():
    async def main():
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        start = loop.time()
        ticker = asyncio.create_task(asyncio.sleep(0.2))  # a busy loop would have many of these
        threading.Timer(0.05, fut.set_result, (1149,)).start()
        await fut
        woke = loop.time() - start
        await ticker
        return woke

    assert 0.15 <= asyncio.run(main()) <= 0.4  # set at 50 ms, noticed when the 200 ms timer fires


# ---- rung 5 ------------------------------------------------------------------------


def test_quiz_snapshot_swap_makes_no_calls_and_no_waits():
    lines = (HERE / "out" / "four_ways.txt").read_text().splitlines()
    snapshot = next(line for line in lines if line.strip().startswith("Snapshot"))
    assert "calls during the burst: 0; slowest wait   0 ms" in snapshot


def test_order_gateway_versions_are_numbered_in_build_order():
    names = sorted(HERE.glob("gateway_v*.py"), key=lambda p: int(p.stem.removeprefix("gateway_v")))
    assert [p.stem for p in names] == [f"gateway_v{n}" for n in range(9)]

"""The behaviours the page claims about generators, coroutines and the toy loop."""

import asyncio
import contextlib
import heapq
import io
import sys
import time
import warnings

import gateway_v1
import loop_step2
import pytest
from sellers import BUDGET_MS, SELLERS, SellerError
from toyloop import Sleep, ToyLoop, sleep


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def test_runs_on_the_series_baseline():
    assert sys.version_info >= (3, 14)


def test_sellers_are_the_series_numbers():
    assert [(s.name, s.latency_ms, s.price) for s in SELLERS] == [
        ("seller-a", 80, 1249),
        ("seller-b", 120, 1199),
        ("seller-c", 150, 1229),
        ("seller-d", 200, 1215),
        ("seller-e", 900, 1149),
    ]
    assert BUDGET_MS == 250
    assert sum(s.latency_ms for s in SELLERS) == 1450  # one after another
    assert max(s.latency_ms for s in SELLERS) == 900  # all overlapping


# ---- generators -------------------------------------------------------------


def test_generator_body_does_not_run_until_next():
    ran = []

    def gen():
        ran.append(True)
        yield 1

    g = gen()
    assert ran == []
    assert next(g) == 1 and ran == [True]


def test_close_returns_the_generators_return_value():
    def counter():
        n = 0
        try:
            while True:
                yield
                n += 1
        except GeneratorExit:
            return n

    c = counter()
    next(c)
    c.send(None)
    assert c.close() == 1  # Python 3.13+ behaviour
    assert c.close() is None


def test_close_raises_if_the_generator_yields_again():
    def stubborn():
        with contextlib.suppress(GeneratorExit):
            yield
        yield  # yields again instead of stopping

    s = stubborn()
    next(s)
    with pytest.raises(RuntimeError):
        s.close()


def test_throw_uncaught_propagates_to_the_caller():
    def gen():
        yield

    g = gen()
    next(g)
    with pytest.raises(ValueError):
        g.throw(ValueError("boom"))


# ---- coroutines -------------------------------------------------------------


def test_awaiting_a_coroutine_twice_is_an_error():
    async def inner():
        return 1

    async def outer():
        c = inner()
        await c
        await c

    with pytest.raises(RuntimeError):
        outer().send(None)


def test_coroutine_send_reaches_the_innermost_yield():
    async def handler():
        return await gateway_v1.ask_seller(type("L", (), {"now": 0})(), SELLERS[0], "x")

    coro = handler()
    assert coro.send(None) == ("sleep", 80)
    with pytest.raises(StopIteration) as stop, contextlib.redirect_stdout(io.StringIO()):
        coro.send(None)
    assert stop.value.value.price == 1249


def test_dropped_coroutine_warns_never_awaited():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sleep(10)
        import gc

        gc.collect()
    assert any("was never awaited" in str(w.message) for w in caught)


# ---- the toy loop -----------------------------------------------------------


def test_step2_heap_states_match_the_solved_example():
    seen = []

    class Watched(loop_step2.Loop):
        def run(self):
            original = heapq.heappush

            def push(heap, item):
                original(heap, item)
                seen.append([(at, gen.gi_frame.f_locals["name"]) for at, _, gen in sorted(heap)])

            loop_step2.heapq.heappush = push
            try:
                super().run()
            finally:
                loop_step2.heapq.heappush = original

    loop = Watched()
    loop.spawn(loop_step2.sleeper(loop, "A", [30, 50]))
    loop.spawn(loop_step2.sleeper(loop, "B", [20]))
    loop.spawn(loop_step2.sleeper(loop, "C", [40]))
    quiet(loop.run)
    assert seen == [
        [(30, "A")],
        [(20, "B"), (30, "A")],
        [(20, "B"), (30, "A"), (40, "C")],
        [(40, "C"), (80, "A")],
    ]
    assert loop.now == 80


def test_v1_overlaps_waits_to_the_slowest_seller():
    best, missed, loop = quiet(gateway_v1.compare, "kettle-1l")
    assert (best.seller, best.price, missed, loop.now) == ("seller-e", 1149, [], 900)


def test_budget_returns_cheapest_in_time_and_lists_the_rest():
    best, missed, loop = quiet(gateway_v1.compare, "kettle-1l", budget_ms=BUDGET_MS)
    assert (best.seller, best.price, missed, loop.now) == ("seller-b", 1199, ["seller-e"], 250)


def test_budget_closes_the_unfinished_coroutine():
    loop = ToyLoop()
    cleaned = []

    async def slow():
        try:
            await sleep(900)
        finally:
            cleaned.append(loop.now)

    task = loop.spawn(slow(), "seller-e")
    loop.run(until=250)
    task.coro.close()
    assert cleaned == [250] and task.coro.cr_frame is None


def test_trace_of_v1_is_what_the_page_tabulates():
    _, _, loop = quiet(gateway_v1.compare, "kettle-1l")
    assert [(now, what) for now, what, *_ in loop.trace][:6] == [
        (0, "seller-a sleeps 80 ms"),
        (0, "seller-b sleeps 120 ms"),
        (0, "seller-c sleeps 150 ms"),
        (0, "seller-d sleeps 200 ms"),
        (0, "seller-e sleeps 900 ms"),
        (80, "wake seller-a"),
    ]
    assert len(loop.trace) == 15


# ---- what the toy loop gets wrong --------------------------------------------


async def blocking_ask(loop, seller, item, faulty=()):
    if seller.name == "seller-b":
        time.sleep(0.3)
    return await gateway_v1.ask_seller(loop, seller, item, faulty)


def test_one_blocking_call_delays_every_seller():
    best, missed, loop = quiet(gateway_v1.compare, "kettle-1l", ask=blocking_ask)
    assert 1180 <= loop.now <= 1230  # 900 + about 300 ms of blocking
    assert loop.warnings and loop.warnings[0].startswith("slow step: seller-b ran for")


def test_blocking_call_blows_the_budget_and_loses_every_offer():
    best, missed, loop = quiet(gateway_v1.compare, "kettle-1l", budget_ms=BUDGET_MS, ask=blocking_ask)
    assert best is None and len(missed) == 5 and loop.now >= 300


def test_one_failing_seller_ends_the_whole_request():
    with pytest.raises(SellerError, match="seller-c failed"):
        quiet(gateway_v1.compare, "kettle-1l", budget_ms=BUDGET_MS, faulty={"seller-c"})


def test_failure_happens_at_150ms_after_a_and_b_answered():
    loop = ToyLoop()
    tasks = [loop.spawn(gateway_v1.ask_seller(loop, s, "x", faulty={"seller-c"}), s.name) for s in SELLERS]
    with pytest.raises(SellerError), contextlib.redirect_stdout(io.StringIO()):
        loop.run(until=BUDGET_MS)
    assert loop.now == 150
    assert [t.name for t in tasks if t.done] == ["seller-a", "seller-b"]
    for t in tasks:
        t.coro.close()


def test_asyncio_awaitables_do_not_work_on_the_toy_loop():
    async def uses_asyncio():
        await asyncio.sleep(0.08)

    loop = ToyLoop()
    loop.spawn(uses_asyncio(), "seller-a")
    with pytest.raises(RuntimeError, match="no running event loop"):
        loop.run()


def test_unknown_request_is_rejected():
    class Odd:
        def __await__(self):
            yield "read socket 5"

    async def uses_odd():
        await Odd()

    loop = ToyLoop()
    loop.spawn(uses_odd(), "seller-a")
    with pytest.raises(TypeError, match="cannot handle 'read socket 5'"):
        loop.run()


def test_sleep_awaitable_yields_the_request_tuple():
    assert next(Sleep(80).__await__()) == ("sleep", 80)

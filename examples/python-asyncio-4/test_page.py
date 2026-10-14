"""The page shows what the code does: tables, measured numbers, snippets and check answers."""

import contextlib
import io
import json
import re
import time
from pathlib import Path

import gateway_v1
import loop_step2
import pytest
from gateway_v1 import compare
from sellers import SELLERS
from toyloop import ToyLoop
from trace_rows import rows

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-1"
BODY = (CONTENT / "body.html").read_text()


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def test_gateway_v1_trace_table_is_on_the_page():
    _, _, loop = quiet(compare, "kettle-1l")
    for row in rows(loop.trace):
        assert row in BODY, row


def test_measured_thread_costs_are_the_ones_the_page_shows():
    m = json.loads((HERE / "measured.json").read_text())
    assert f"about {m['virtual_kib_per_thread']:,} KiB" in BODY
    assert f"about {m['resident_kib_per_thread']} KiB" in BODY
    assert f"about {m['start_us_per_thread']} µs" in BODY
    assert f"{m['stack_limit_kib']:,} KiB" in BODY


def test_inline_snippets_match_the_tested_files():
    for snippet in re.findall(r'data-verified="spec"[^>]*>\s*<pre><code>(.*?)</code></pre>', BODY, re.S):
        code = snippet.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        sources = (HERE / "toyloop.py").read_text() + (HERE / "gateway_v1.py").read_text()
        assert code in sources, code[:80]


def test_meta_holds_the_ten_page_plan_with_slugs_only_for_existing_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    related = meta["related"]
    assert len(related) == 10
    for i, entry in enumerate(related, 1):
        assert entry["label"].startswith(f"Python async, Part {i}:")
        if "slug" in entry:
            assert (CONTENT.parent / entry["slug"] / "meta.json").is_file()


# ---- answers to the page's checks -------------------------------------------


def last_line(budget):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        gateway_v1.report(*compare("kettle-1l", budget_ms=budget))
    return out.getvalue().strip().splitlines()[-1]


def test_quiz_160ms_budget():
    assert last_line(160) == "cheapest: seller-b at 1,199 after 160 ms; missed: seller-d, seller-e"


def test_predict_175ms_budget():
    assert last_line(175) == "cheapest: seller-b at 1,199 after 175 ms; missed: seller-d, seller-e"


def test_quiz_running_the_loop_after_each_spawn_adds_the_waits_up():
    loop = ToyLoop()
    with contextlib.redirect_stdout(io.StringIO()):
        for s in SELLERS:
            loop.spawn(gateway_v1.ask_seller(loop, s, "x"), s.name)
            loop.run()
    assert loop.now == 1450


def test_predict_seller_e_blocking_loses_every_offer():
    async def e_blocks(loop, seller, item, faulty=()):
        if seller.name == "seller-e":
            time.sleep(0.3)
        return await gateway_v1.ask_seller(loop, seller, item, faulty)

    best, missed, loop = quiet(compare, "kettle-1l", budget_ms=250, ask=e_blocks)
    assert best is None and len(missed) == 5 and 300 <= loop.now <= 330


def test_predict_fault_in_seller_e_never_fires_within_the_budget():
    best, missed, loop = quiet(compare, "kettle-1l", budget_ms=250, faulty={"seller-e"})
    assert (best.seller, missed, loop.now) == ("seller-b", ["seller-e"], 250)


def test_predict_timer_heap_with_a_fourth_job():
    loop = loop_step2.Loop()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        loop.spawn(loop_step2.sleeper(loop, "A", [30, 50]))
        loop.spawn(loop_step2.sleeper(loop, "B", [20]))
        loop.spawn(loop_step2.sleeper(loop, "C", [40]))
        loop.spawn(loop_step2.sleeper(loop, "D", [10, 60]))
        loop.run()
    done = [line.split()[0] + " " + line.split()[2] for line in out.getvalue().splitlines() if "done" in line]
    assert done == ["20 B", "40 C", "70 D", "80 A"] and loop.now == 80


def test_quiz_await_on_a_non_iterator_raises_typeerror():
    class Tick:
        def __await__(self):
            return 42

    async def use():
        await Tick()

    with pytest.raises(TypeError):
        use().send(None)


def test_predict_throw_into_yield_from_reaches_the_inner_generator():
    from gen_yield_from import parcel_desk

    desk = parcel_desk()
    desk.send(None)
    with pytest.raises(ValueError, match="scale broken"):
        desk.throw(ValueError("scale broken"))


def test_predict_countdown_two():
    from gen_basics import countdown

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        g = countdown(2)
        assert out.getvalue() == ""
        assert [next(g), next(g)] == [2, 1]
        with pytest.raises(StopIteration) as stop:
            next(g)
    assert stop.value.value == "lift-off" and out.getvalue() == "starting\n"


def test_quiz_bill_sends():
    from gen_send import bill

    b = bill()
    assert [b.send(None), b.send(30), b.send(30)] == [0, 30, 60]

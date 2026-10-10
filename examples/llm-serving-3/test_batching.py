"""Every number the page quotes from the simulator, the toy timeline and the steady-state estimator."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import timeline as tl
from continuous import run_continuous
from kv_cache import decode_step
from simulate import H100, KV_TOKENS, LLAMA_8B, compare, summarize
from static import run_static
from steady_state import estimate
from step import step_seconds
from workload import Request, make_trace

HERE = Path(__file__).parent
BODY = HERE.parent.parent / "content" / "llm-serving-3" / "body.html"


@pytest.mark.parametrize("name", ["gpus.py", "estimate.py", "models.py", "kv_cache.py"])
def test_part2_estimator_is_copied_unchanged(name):
    assert (HERE / name).read_text() == (HERE.parent / "llm-serving-2" / name).read_text()


# ---- the step model ----
def test_decode_only_step_matches_part2():
    for batch, ctx in [(1, 2300), (64, 2000), (181, 2300)]:
        expect = decode_step(H100, LLAMA_8B, batch, ctx)["seconds"]
        assert step_seconds(H100, LLAMA_8B, [], [ctx] * batch) == pytest.approx(expect)


def test_one_weight_read_shared_by_the_whole_batch():
    one = step_seconds(H100, LLAMA_8B, [], [1000])
    sixteen = step_seconds(H100, LLAMA_8B, [], [1000] * 16)
    assert one == pytest.approx(0.00482, abs=1e-5)
    assert sixteen == pytest.approx(0.00540, abs=1e-5)  # 16x the tokens for 12% more time
    assert 16 * one / sixteen == pytest.approx(14.3, abs=0.05)


def test_a_prefill_slows_every_decode_in_its_step():
    decode_only = step_seconds(H100, LLAMA_8B, [], [1000] * 16)
    with_prompt = step_seconds(H100, LLAMA_8B, [2000], [1000] * 16)
    full_budget = step_seconds(H100, LLAMA_8B, [8000], [1000] * 16)
    assert with_prompt == pytest.approx(0.0337, abs=1e-4)
    assert with_prompt / decode_only == pytest.approx(6.2, abs=0.05)
    assert full_budget == pytest.approx(0.147, abs=5e-4)
    assert full_budget / decode_only == pytest.approx(27, abs=0.5)


# ---- worked example: one static batch of four ----
def four():
    return [Request(0.0, p, o) for p, o in [(300, 50), (800, 120), (1200, 300), (2000, 600)]]


def test_static_batch_of_four_wastes_about_half_its_work():
    reqs = four()
    run = run_static(reqs, H100, LLAMA_8B, 4)
    assert 4 * 2000 == 8000 and sum(r.prompt for r in reqs) == 4300  # prefill rows padded vs real
    assert pytest.approx(0.4625) == 1 - 4300 / 8000
    assert (4 * 599, 49 + 119 + 299 + 599) == (2396, 1066)  # decode row-steps run vs useful
    assert pytest.approx(0.555, abs=5e-4) == 1 - 1066 / 2396
    assert run["padding_fraction"] == pytest.approx(0.484, abs=5e-4)
    assert step_seconds(H100, LLAMA_8B, [2000] * 4, []) == pytest.approx(0.1336, abs=1e-4)
    assert step_seconds(H100, LLAMA_8B, [300, 800, 1200, 2000], []) == pytest.approx(0.0712, abs=1e-4)
    a = reqs[0]
    assert a.last == pytest.approx(0.383, abs=5e-4)  # its own last token
    assert a.done == pytest.approx(3.210, abs=5e-4)  # but it returns with the slowest request
    assert a.done / a.last == pytest.approx(8.4, abs=0.05)


def test_same_four_under_continuous_batching():
    reqs = four()
    run_continuous(reqs, H100, LLAMA_8B, 4, 8192)
    assert reqs[0].done == pytest.approx(0.314, abs=5e-4)
    assert reqs[0].first == pytest.approx(0.0712, abs=1e-4)  # no padding in the prefill
    assert max(r.done for r in reqs) == pytest.approx(3.006, abs=5e-4)


# ---- the six-request timeline ----
def test_timeline_counts():
    s, c = tl.static(), tl.continuous()
    assert (len(s), len(c)) == (11, 8)
    assert (tl.count(s, "pad"), tl.count(s, "wait")) == (10, 3)
    assert (tl.count(c, "pad"), tl.count(c, "wait"), tl.count(c, "")) == (0, 0, 4)
    assert tl.count(s, "d") == tl.count(c, "d") == 14  # the same useful work
    finish = {r: (tl.finish_step(s, r), tl.finish_step(c, r)) for r in "ABCDEF"}
    assert finish == {"A": (2, 1), "B": (6, 5), "C": (3, 3), "D": (8, 3), "E": (10, 7), "F": (9, 6)}


def test_page_timeline_matches_the_code():
    pattern = r'class="ts-slots".*?<script type="application/json">(.*?)</script>'
    spec = re.search(pattern, BODY.read_text(), re.S)
    data = json.loads(spec.group(1))
    assert data["lanes"][0]["cols"] == tl.static()
    assert data["lanes"][1]["cols"] == tl.continuous()
    assert [[r["id"], r["arrives"], r["tokens"]] for r in data["requests"]] == [list(r) for r in tl.REQUESTS]
    assert len(data["captions"]) == len(tl.static())


# ---- simulator: 400 requests, batch limit 16, Llama 3.1 8B on one H100 ----
def test_kv_budget_is_part2s():
    assert pytest.approx(416_565, abs=1) == KV_TOKENS


def test_trace_is_reproducible_and_as_described():
    a, b = make_trace(4, 400), make_trace(4, 400)
    assert [(r.arrival, r.prompt, r.output) for r in a] == [(r.arrival, r.prompt, r.output) for r in b]
    assert all(100 <= r.prompt <= 2000 and 20 <= r.output <= 500 for r in a)


def test_at_4_requests_per_second_both_keep_up_but_static_answers_100x_later():
    s, c = compare(4, 400, 16).values()
    assert s["output_tokens_per_s"] == pytest.approx(1040, abs=1)
    assert c["output_tokens_per_s"] == pytest.approx(1072, abs=1)
    assert (s["ttft_mean_s"], s["ttft_p99_s"]) == pytest.approx((2.55, 5.25), abs=0.005)
    assert (c["ttft_mean_s"], c["ttft_p99_s"]) == pytest.approx((0.0197, 0.0415), abs=5e-4)
    assert s["ttft_mean_s"] / c["ttft_mean_s"] == pytest.approx(130, abs=1)
    assert (s["tpot_mean_s"], c["tpot_mean_s"]) == pytest.approx((0.00603, 0.00533), abs=5e-5)
    assert (s["e2e_mean_s"], c["e2e_mean_s"]) == pytest.approx((5.43, 1.41), abs=0.005)
    assert s["gpu_idle_fraction"] == pytest.approx(0.16, abs=0.005)
    assert c["gpu_idle_fraction"] == pytest.approx(0.002, abs=0.0005)
    assert s["padding_fraction"] == pytest.approx(0.475, abs=5e-4)
    assert c["worst_gap_s"] == pytest.approx(0.0576, abs=5e-4)  # a decode step shared with prefills
    assert s["preemptions"] == c["preemptions"] == 0


def test_at_8_requests_per_second_static_falls_behind():
    s, c = compare(8, 400, 16).values()
    assert s["output_tokens_per_s"] == pytest.approx(1224, abs=1)
    assert c["output_tokens_per_s"] == pytest.approx(2079, abs=1)
    assert s["ttft_mean_s"] == pytest.approx(17.4, abs=0.05)
    assert c["ttft_mean_s"] == pytest.approx(0.087, abs=5e-4)


def run_40(max_num_seqs, kv_tokens=KV_TOKENS):
    reqs = make_trace(40, 400)
    return summarize(reqs, run_continuous(reqs, H100, LLAMA_8B, max_num_seqs, 8192, kv_tokens))


def test_max_num_seqs_trades_tpot_against_queueing():
    rows = {n: run_40(n) for n in (32, 128, 512)}
    assert [round(rows[n]["output_tokens_per_s"]) for n in (32, 128, 512)] == [4029, 7005, 7411]
    assert [round(rows[n]["tpot_mean_s"] * 1e3, 1) for n in (32, 128, 512)] == [7.5, 14.1, 17.8]
    assert [round(rows[n]["ttft_mean_s"], 2) for n in (32, 128, 512)] == [6.38, 0.60, 0.07]


def test_a_small_kv_budget_causes_preemptions():
    full, small = run_40(512), run_40(512, kv_tokens=100_000)
    assert full["preemptions"] == 0
    assert small["preemptions"] == 51
    assert small["output_tokens_per_s"] == pytest.approx(5930, abs=1)
    assert small["ttft_mean_s"] == pytest.approx(1.89, abs=0.005)


# ---- steady-state estimator (the calculator) ----
def test_estimator_default_scenario():
    e = estimate(H100, LLAMA_8B, 10, 1000, 250, 1024)
    assert not e["overloaded"]
    assert e["running"] == pytest.approx(15.3, abs=0.05)
    assert e["tpot_s"] == pytest.approx(0.00614, abs=5e-6)
    assert e["ttft_s"] == pytest.approx(0.0198, abs=5e-5)
    assert e["output_tokens_per_s"] == 2500
    assert e["kv_used_bytes"] == pytest.approx(2.25e9, abs=0.005e9)
    assert e["max_running"] == 333


@pytest.mark.parametrize(
    "cap,tokens_per_s,tpot_ms",
    [(1, 206, 4.87), (8, 1461, 5.50), (32, 4244, 7.57), (128, 8796, 14.61), (333, 14606, 22.89)],
)
def test_bigger_batches_raise_tokens_per_s_and_tpot(cap, tokens_per_s, tpot_ms):
    e = estimate(H100, LLAMA_8B, 1e6, 1000, 250, cap)  # demand far above capacity: every slot full
    assert e["overloaded"] and e["running"] == cap
    assert round(e["output_tokens_per_s"]) == tokens_per_s
    assert round(e["tpot_s"] * 1e3, 2) == tpot_ms


def test_kv_budget_caps_the_batch_at_333():
    e = estimate(H100, LLAMA_8B, 1e6, 1000, 250, 1024)
    assert e["running"] == 333
    assert e["kv_used_bytes"] == pytest.approx(49.1e9, abs=0.05e9)


def test_estimator_agrees_with_the_simulator_below_capacity():
    for rate in (2, 10, 20):
        reqs = make_trace(rate, 600, prompt=(1000, 1000), output=(250, 250))
        sim = summarize(reqs, run_continuous(reqs, H100, LLAMA_8B, 1024, 8192, KV_TOKENS))
        est = estimate(H100, LLAMA_8B, rate, 1000, 250, 1024)
        assert est["tpot_s"] == pytest.approx(sim["tpot_mean_s"], rel=0.07)
        assert est["output_tokens_per_s"] == pytest.approx(sim["output_tokens_per_s"], rel=0.06)
        assert est["ttft_s"] <= sim["ttft_mean_s"] * 1.01  # it leaves out queueing, so it runs low


def test_cli_compares_both_policies():
    out = subprocess.run(
        [sys.executable, "simulate.py", "4", "400", "16"], cwd=HERE, capture_output=True, text=True
    ).stdout
    assert "static:" in out and "continuous:" in out and "ttft_p99_s" in out


# ---- numbers quoted in checks, the trade-off part and the drill ----
def test_quiz_one_long_answer_wastes_87_percent():
    run, useful = 1999 * 8, 7 * 19 + 1999
    assert (run, useful) == (15_992, 2_132)
    assert 1 - useful / run == pytest.approx(0.867, abs=5e-4)


def test_equal_lengths_leave_no_padding():
    reqs = make_trace(4, 400, prompt=(1000, 1000), output=(200, 200))
    assert run_static(reqs, H100, LLAMA_8B, 16)["padding_fraction"] == pytest.approx(0, abs=1e-12)


def test_at_saturation_static_gets_about_half_of_continuous():
    s, c = compare(16, 400, 16).values()
    assert round(s["output_tokens_per_s"]) == 1231
    assert round(c["output_tokens_per_s"]) == 2511
    assert s["output_tokens_per_s"] / c["output_tokens_per_s"] == pytest.approx(0.49, abs=0.005)


def test_trade_off_ratios_from_1_to_333():
    one, full = (estimate(H100, LLAMA_8B, 1e6, 1000, 250, n) for n in (1, 333))
    assert full["output_tokens_per_s"] / one["output_tokens_per_s"] == pytest.approx(71, abs=0.5)
    assert full["tpot_s"] / one["tpot_s"] == pytest.approx(4.7, abs=0.05)


def test_drill_one_chat_service():
    e30, e35 = (estimate(H100, LLAMA_8B, r, 1000, 250, 1024) for r in (30, 35))
    assert not e30["overloaded"] and not e35["overloaded"]
    assert e30["running"] == pytest.approx(90, abs=0.5)
    assert e30["tpot_s"] == pytest.approx(0.0121, abs=5e-5)
    assert e30["kv_used_bytes"] == pytest.approx(13.3e9, abs=0.05e9)
    assert e35["tpot_s"] == pytest.approx(0.0145, abs=5e-5)
    assert e35["running"] == pytest.approx(127, abs=0.5)


def test_worker_pool_quiz_about_50_long_requests_fit():
    budget = 80e9 * 0.92 - 16e9 - 3e9
    per_request = 8000 * 131_072
    assert per_request == pytest.approx(1.05e9, abs=0.005e9)
    assert budget / per_request == pytest.approx(52, abs=0.5)

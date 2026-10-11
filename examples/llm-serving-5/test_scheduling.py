"""Every number and behaviour the Part 5 page quotes from the simulator and the calculator."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from budget_figure import figure
from chunk_budget import chunk_steps, estimate
from scenarios import H100, KV_TOKENS, LLAMA_8B, load, stall, tenants
from scheduler import Req, run
from slo import is_good, summarize, tpot
from step import step_seconds

HERE = Path(__file__).parent
BODY = (HERE.parent.parent / "content" / "llm-serving-5" / "body.html").read_text()
UI_JS = (HERE.parent.parent / "ui" / "ts.js").read_text()


@pytest.mark.parametrize("name", ["gpus.py", "models.py", "estimate.py", "kv_cache.py", "workload.py"])
def test_part3_models_are_copied_unchanged(name):
    assert (HERE / name).read_text() == (HERE.parent / "llm-serving-3" / name).read_text()


def test_step_model_matches_part3_when_chunks_start_at_zero():
    sys.path.insert(0, str(HERE.parent / "llm-serving-3"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("step3", HERE.parent / "llm-serving-3" / "step.py")
    step3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(step3)
    for prefills, decodes in [([2000], [1000] * 16), ([8000], [1000] * 16), ([300, 800], [])]:
        assert step_seconds(H100, LLAMA_8B, [(0, p) for p in prefills], decodes) == pytest.approx(
            step3.step_seconds(H100, LLAMA_8B, prefills, decodes)
        )


def test_later_chunks_cost_more_than_earlier_ones():
    first = step_seconds(H100, LLAMA_8B, [(0, 8172)], [1000] * 20)
    later = step_seconds(H100, LLAMA_8B, [(5 * 8172, 8172)], [1000] * 20)
    assert later > first


# ---- part 1: the stall ----
def test_decode_only_step_and_unchunked_stall():
    assert step_seconds(H100, LLAMA_8B, [], [1000] * 20) == pytest.approx(0.0056, abs=5e-5)
    off = stall(65536, chunked=False)
    assert off["worst_itl_s"] == pytest.approx(1.471, abs=5e-4)
    assert off["long_ttft_s"] == pytest.approx(1.471, abs=5e-4)
    assert [s["prefill"] for s in off["steps"] if s["prefill"]] == [50_000]


def test_doubling_the_prompt_more_than_doubles_the_stall():
    one = step_seconds(H100, LLAMA_8B, [(0, 50_000)], [1000] * 20)
    two = step_seconds(H100, LLAMA_8B, [(0, 100_000)], [1000] * 20)
    assert two / one > 2


def test_unchunked_needs_the_whole_prompt_in_one_step():
    streams = [Req(0.0, 1000, 10, cached=1000, made=1, scheduled=0.0) for _ in range(2)]
    long = Req(0.0, 5000, 2)
    run([long], H100, LLAMA_8B, budget=4096, chunked=False, running=streams)
    assert long.scheduled > 0  # it could not start until the streams finished and freed budget


# ---- part 2: chunked prefill and the figure ----
def test_chunks_at_8192():
    s = stall(8192)
    chunks = [st["prefill"] for st in s["steps"] if st["prefill"]]
    assert chunks == [8172] * 6 + [968]
    assert s["steps"][0]["dt"] == pytest.approx(0.150, abs=5e-4)
    assert s["worst_itl_s"] == pytest.approx(0.327, abs=5e-4)
    assert s["long_ttft_s"] == pytest.approx(1.473, abs=5e-4)
    assert all(st["decode"] == 20 for st in s["steps"][:7])  # every stream got a token every step


def test_page_figure_is_generated_from_the_simulator():
    assert figure() in BODY


# ---- part 3: the budget table ----
@pytest.mark.parametrize(
    "budget,steps,worst_ms,ttft_s",
    [(16384, 4, 620, 1.472), (8192, 7, 327, 1.473), (2048, 25, 84, 1.479), (512, 102, 21, 1.505),
     (256, 212, 10, 1.592), (128, 463, 7.9, 3.109)],
)  # fmt: skip
def test_budget_table(budget, steps, worst_ms, ttft_s):
    s = stall(budget)
    assert sum(1 for st in s["steps"] if st["prefill"]) == steps
    assert s["worst_itl_s"] * 1000 == pytest.approx(worst_ms, abs=0.5 if worst_ms > 9 else 0.05)
    assert s["long_ttft_s"] == pytest.approx(ttft_s, abs=5e-4)


def test_budget_table_prose_ratios():
    base = stall(65536, chunked=False)["long_ttft_s"]
    assert round(100 * (stall(512)["long_ttft_s"] / base - 1)) == 2
    assert round(100 * (stall(256)["long_ttft_s"] / base - 1)) == 8
    assert stall(128)["long_ttft_s"] / base > 2
    assert stall(2048)["worst_itl_s"] < 0.1 < stall(8192)["worst_itl_s"]  # the quiz


# ---- part 4: head-of-line blocking ----
def test_chat_behind_the_long_prompt():
    a, b = stall(8192, with_chat=True), stall(2048, with_chat=True)
    assert a["chat_ttft_s"] == pytest.approx(1.471, abs=5e-4)
    assert b["chat_ttft_s"] == pytest.approx(1.477, abs=5e-4)
    capped = stall(8192, long_prefill=2048, with_chat=True)
    assert capped["chat_ttft_s"] == pytest.approx(0.0695, abs=5e-4)
    assert a["long_ttft_s"] == pytest.approx(1.481, abs=5e-4)
    assert capped["long_ttft_s"] == pytest.approx(1.488, abs=5e-4)
    assert capped["worst_itl_s"] == pytest.approx(0.086, abs=5e-4)


def test_prefill_cap_is_skipped_for_a_lone_request():
    alone = Req(0.0, 5000, 2)
    res = run([alone], H100, LLAMA_8B, budget=8192, long_prefill=1000)
    assert res["steps"][0]["prefill"] == 5000


def test_head_of_queue_that_does_not_fit_blocks_those_behind():
    holder = Req(0.0, 500, 5, cached=500, made=1, scheduled=0.0)  # holds 500 of 1,000 KV slots
    big, small = Req(0.0, 900, 2), Req(0.0, 10, 2)
    run([big, small], H100, LLAMA_8B, budget=8192, kv_tokens=1000, running=[holder])
    assert big.scheduled > 0  # waited for the holder to finish
    assert small.scheduled >= big.scheduled  # small would have fit, but did not jump ahead


# ---- part 5: goodput ----
@pytest.fixture(scope="module")
def loads():
    return {"normal": load(4), "ten": load(40), "capped": load(40, max_queued=300)}


def test_goodput_table(loads):
    n, t = loads["normal"], loads["ten"]
    assert n["requests_per_s"] == pytest.approx(4.05, abs=5e-3)
    assert n["goodput_per_s"] == pytest.approx(4.05, abs=5e-3)
    assert n["slo_attainment"] == 1.0
    assert n["ttft_p99_s"] == pytest.approx(0.051, abs=5e-4)
    assert t["requests_per_s"] == pytest.approx(34.6, abs=0.05)
    assert t["goodput_per_s"] == pytest.approx(10.0, abs=0.05)
    assert round(100 * t["slo_attainment"]) == 29
    assert t["ttft_p99_s"] == pytest.approx(7.56, abs=5e-3)
    assert round(t["requests_per_s"] / n["requests_per_s"]) == 9  # "almost ninefold"
    assert t["goodput_per_s"] / n["goodput_per_s"] == pytest.approx(2.5, abs=0.05)


def test_tpot_hides_a_single_stall():
    r = Req(0.0, 100, 300)
    r.first, r.last = 0.0, 298 * 0.00556 + 0.327
    assert tpot(r) == pytest.approx(0.0066, abs=5e-5)
    assert is_good(r, 1.0, 0.05)


def test_goodput_needs_every_slo():
    r = Req(0.0, 100, 11)
    r.first, r.last = 0.5, 0.5 + 10 * 0.08  # TTFT fine, TPOT 80 ms
    r.done = r.last
    assert not is_good(r, 1.0, 0.05)
    assert summarize([r], 1.0, 0.05)["goodput_per_s"] == 0


# ---- part 6: priority ----
@pytest.fixture(scope="module")
def tenant_runs():
    return {
        "fcfs": tenants(),
        "priority": tenants(policy="priority"),
        "cap": tenants(long_prefill=2048),
        "small_prio": tenants(budget=2048, policy="priority"),
        "limited": tenants(rate_b=0.1),
        "alone": tenants(rate_b=1e-9),
    }


@pytest.mark.parametrize(
    "case,ttft,itl_ms,met,b_ttft",
    [("fcfs", 1.99, 221, 86, 2.25), ("priority", 0.91, 223, 97, 2.52), ("cap", 0.71, 141, 98, 3.03),
     ("small_prio", 0.82, 64, 100, 2.52), ("limited", 0.88, 31, 99.6, 1.63)],
)  # fmt: skip
def test_tenant_table(tenant_runs, case, ttft, itl_ms, met, b_ttft):
    s = tenant_runs[case]
    assert s["a_ttft_p99_s"] == pytest.approx(ttft, abs=5e-3)
    assert s["a_itl_p99_s"] * 1000 == pytest.approx(itl_ms, abs=0.5)
    assert 100 * s["a_slo_attainment"] == pytest.approx(met, abs=0.5 if met != 99.6 else 0.05)
    assert s["b_ttft_p99_s"] == pytest.approx(b_ttft, abs=5e-3)


def test_tenant_baseline(tenant_runs):
    s = tenant_runs["alone"]
    assert s["b_requests"] == 0
    assert s["a_ttft_p99_s"] == pytest.approx(0.057, abs=5e-4)
    assert s["a_itl_p99_s"] * 1000 == pytest.approx(28, abs=0.5)
    assert tenant_runs["fcfs"]["b_requests"] == 52  # one every ~2 s over the trace


def test_priority_orders_queue_but_does_not_preempt_running():
    streams = [Req(0.0, 1000, 50, cached=1000, made=1, scheduled=0.0, priority=5) for _ in range(3)]
    vip = Req(0.0, 100, 2, priority=0)
    later = Req(0.0, 100, 2, priority=9)
    run([later, vip], H100, LLAMA_8B, budget=8192, policy="priority", running=streams)
    assert all(s.preempted == 0 for s in streams)
    assert vip.scheduled <= later.scheduled


def test_preemption_victims():
    def setup(policy):
        a = Req(0.0, 60, 40, priority=0)
        b = Req(0.001, 60, 40, priority=5)
        c = Req(0.002, 60, 40, priority=1)
        run([a, b, c], H100, LLAMA_8B, budget=8192, kv_tokens=200, policy=policy)
        return a, b, c

    a, b, c = setup("fcfs")
    assert c.preempted >= 1 and a.preempted == 0  # the last admitted goes first
    a, b, c = setup("priority")
    assert b.preempted >= 1 and a.preempted == 0  # the largest priority value goes first


# ---- part 7: queue caps ----
def test_queue_cap(loads):
    t, c = loads["ten"], loads["capped"]
    assert c["rejected"] == 228 and round(100 * 228 / 3000, 1) == 7.6
    assert c["requests_per_s"] == pytest.approx(35.2, abs=0.05)
    assert c["goodput_per_s"] == pytest.approx(35.2, abs=0.05)
    assert c["ttft_p99_s"] == pytest.approx(0.22, abs=5e-3)
    assert t["preemptions"] == 148 and c["preemptions"] == 0
    assert round(c["goodput_per_s"] / t["goodput_per_s"], 1) == 3.5


# ---- part 9: calculator ----
def test_calculator_defaults():
    e = estimate(H100, LLAMA_8B)
    assert e["decode_s"] == pytest.approx(0.0056, abs=5e-5)
    assert e["worst_step_s"] == pytest.approx(0.327, abs=5e-4)
    assert e["long_ttft_s"] == pytest.approx(1.47, abs=5e-3)
    assert e["itl_p99_s"] == pytest.approx(0.0056, abs=5e-5)
    assert e["goodput_per_s"] == e["requests_per_s"] == pytest.approx(11.5, abs=0.05)
    assert 0 < e["late_token_share"] < 0.01
    assert estimate(H100, LLAMA_8B, budget=2048)["worst_step_s"] == pytest.approx(0.084, abs=5e-4)
    busy = estimate(H100, LLAMA_8B, per_min=20)
    assert busy["worst_step_s"] == pytest.approx(0.327, abs=5e-4)
    assert busy["itl_p99_s"] == pytest.approx(0.256, abs=5e-4)


def test_calculator_steps_match_the_simulator():
    sim = [st["dt"] for st in stall(8192)["steps"] if st["prefill"]]
    assert chunk_steps(H100, LLAMA_8B, 8192, 20, 1000, 50_000) == pytest.approx(sim)


def _js_function(name: str) -> str:
    m = re.search(rf"  function {name}\(.*?\n  }}\n", UI_JS, re.S)
    assert m, name
    return m.group(0)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("budget,per_min", [(8192, 2), (2048, 6), (65536, 20), (512, 2)])
def test_calculator_js_matches_python(budget, per_min):
    block = re.search(
        r'<div class="ts-chunkcalc".*?<script type="application/json">(.*?)</script>', BODY, re.S
    )
    spec = json.loads(block.group(1))
    g, m = spec["gpus"][0], spec["models"][0]
    x = {"budget": budget, "streams": 20, "ctx": 1000, "prompt": 50_000, "per_min": per_min, "output": 300,
         "ttft_slo": 2.0, "tpot_slo": 0.05, "itl_slo": 0.1}  # fmt: skip
    src = _js_function("chunkStepSeconds") + _js_function("chunkEstimate")
    src += f"console.log(JSON.stringify(chunkEstimate({json.dumps(g)}, {json.dumps(m)}, {json.dumps(x)})));"
    js = json.loads(subprocess.run(["node", "-e", src], capture_output=True, text=True, check=True).stdout)
    py = estimate(H100, LLAMA_8B, budget=budget, per_min=per_min)
    assert js["decode"] == pytest.approx(py["decode_s"], rel=1e-9)
    assert js["worst"] == pytest.approx(py["worst_step_s"], rel=1e-9)
    assert js["ttft"] == pytest.approx(py["long_ttft_s"], rel=1e-9)
    assert js["p99"] == pytest.approx(py["itl_p99_s"], rel=1e-9)
    assert js["late"] == pytest.approx(py["late_token_share"], rel=1e-9)
    assert js["good"] == pytest.approx(py["goodput_per_s"], rel=1e-9)


def test_calculator_spec_matches_python_hardware():
    block = re.search(
        r'<div class="ts-chunkcalc".*?<script type="application/json">(.*?)</script>', BODY, re.S
    )
    spec = json.loads(block.group(1))
    assert spec["gpus"][0]["tflops"] * 1e12 == H100.peak_flops
    assert spec["gpus"][0]["tbps"] * 1e12 == H100.bandwidth
    m = spec["models"][0]
    assert (m["layers"], m["q_heads"], m["kv_heads"], m["head_dim"]) == (32, 32, 8, 128)
    assert m["params"] * 1e9 == LLAMA_8B.params


# ---- part 10: preemption cost ----
def test_recompute_cost():
    assert step_seconds(H100, LLAMA_8B, [(0, 2400)], []) == pytest.approx(0.040, abs=5e-4)
    assert step_seconds(H100, LLAMA_8B, [], [2400]) == pytest.approx(0.0049, abs=5e-5)
    assert step_seconds(H100, LLAMA_8B, [(0, 2400)], [1000] * 100) == pytest.approx(0.042, abs=5e-4)
    assert step_seconds(H100, LLAMA_8B, [], [1000] * 100) == pytest.approx(0.0087, abs=5e-5)


def test_preempted_request_recomputes_prompt_and_output():
    r = Req(0.0, 60, 40)
    others = [Req(0.0005 * k, 60, 40) for k in range(1, 3)]
    run([r, *others], H100, LLAMA_8B, kv_tokens=200)
    victims = [x for x in [r, *others] if x.preempted]
    assert victims and all(v.done > 0 and v.made == v.output for v in [r, *others])


# ---- part 11: ten times the load ----
def test_ten_times_load_symptoms(loads):
    n, t = loads["normal"], loads["ten"]
    assert n["itl_p99_s"] == pytest.approx(0.019, abs=5e-4)
    assert t["itl_p99_s"] == pytest.approx(0.112, abs=5e-4)
    assert (n["waiting_peak"], t["waiting_peak"]) == (0, 285)
    assert t["queue_p99_s"] == pytest.approx(7.5, abs=5e-3)
    assert round(100 * n["kv_usage_peak"]) == 6 and round(100 * t["kv_usage_peak"]) == 100
    assert pytest.approx(416_565, abs=1) == KV_TOKENS


def test_token_based_limits_quiz():
    assert 32_000 / 500 == 64


def test_cli_prints_scenarios():
    out = subprocess.run([sys.executable, "scenarios.py"], cwd=HERE, capture_output=True, text=True).stdout
    assert "budget   8192" in out and "goodput" in out

"""Every number the Part 7 page quotes from the planner, plus the planner's agreement with Parts 2 to 6."""

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fabric import nic_each_way, nvlink_each_way
from gpus import GPUS
from kv_cache import kv_bytes_per_token
from models import MODELS
from plan import plan
from precision import FP8_SPARSE
from quant import step_seconds as quant_step
from replica import allreduce_seconds, colocated, decode_pool, group_step, prefill_pool, prompt_chunks
from step import step_seconds
from tp import fit, kv_budget, smallest_tp

HERE = Path(__file__).parent
BODY = (HERE.parent.parent / "content" / "llm-serving-7" / "body.html").read_text()
UI_JS = (HERE.parent.parent / "ui" / "ts.js").read_text()
H100, H200 = "h100-sxm", "h200-sxm"
L8, L70 = MODELS["llama-3.1-8b"], MODELS["llama-3.1-70b"]


# ---- built on the series' estimator ----
@pytest.mark.parametrize(
    "name,part",
    [("gpus.py", 2), ("estimate.py", 2), ("models.py", 2), ("kv_cache.py", 2), ("step.py", 5),
     ("precision.py", 6), ("quant.py", 6)],
)  # fmt: skip
def test_series_modules_copied_unchanged(name, part):
    assert (HERE / name).read_text() == (HERE.parent / f"llm-serving-{part}" / name).read_text()


@pytest.mark.parametrize(
    "chunks,decodes",
    [([], [1000] * 20), ([(0, 2000)], []), ([(4000, 1024)], [3000] * 50), ([(0, 500)] * 3, [800])],
)
def test_one_gpu_bf16_step_equals_part5(chunks, decodes):
    ctx = decodes[0] if decodes else 0
    ours = group_step(H100, L8, "bf16", 1, chunks, len(decodes), ctx)
    assert ours == pytest.approx(step_seconds(GPUS[H100], L8, chunks, decodes), rel=1e-12)


@pytest.mark.parametrize("batch,ctx", [(1, 4096), (32, 4096), (256, 500)])
def test_one_gpu_fp8_decode_equals_part6(batch, ctx):
    ours = group_step(H100, L8, "fp8", 1, [], batch, ctx)
    assert ours == pytest.approx(quant_step(H100, L8, "fp8", "fp8", batch, ctx)[0], rel=1e-12)


def test_tp_group_is_a_bigger_gpu_plus_allreduces():
    four = group_step(H100, L70, "bf16", 4, [], 133, 2150)
    reads = (140e9 + 133 * 2150 * 327_680) / (4 * 3.35e12)
    assert four == pytest.approx(reads + allreduce_seconds(H100, L70, 4, 133), rel=1e-12)


# ---- the figures the page quotes ----
def test_link_speeds():
    assert nvlink_each_way(H100) == nvlink_each_way(H200) == 450e9
    assert nic_each_way() == 50e9
    assert FP8_SPARSE[H100] / 2 == 1979


def test_70b_does_not_fit_one_gpu():
    assert L70.params * 2 / 1e9 == 140
    assert kv_budget(H100, L70, "bf16", 1) == 0 and fit(H100, L70, "bf16", 1, 2300) == 0


def test_tp_table_70b_bf16_h100():
    budgets = [round(kv_budget(H100, L70, "bf16", t) / 1e9, 1) for t in (1, 2, 4, 8)]
    assert budgets == [0.0, 1.2, 142.4, 424.8]
    assert [fit(H100, L70, "bf16", t, 2300) for t in (1, 2, 4, 8)] == [0, 1, 188, 563]
    assert smallest_tp(H100, L70, "bf16", 2300) == 2
    assert L70.params * 2 / 4 / 1e9 == 35


def test_tp_table_70b_fp8_and_h200():
    assert [fit(H100, L70, "fp8", t, 2300) for t in (1, 2, 4, 8)] == [1, 188, 563, 1313]
    assert [fit(H200, L70, "bf16", t, 2300) for t in (1, 2, 4, 8)] == [0, 150, 486, 1159]


def test_allreduce_counts_and_costs():
    assert 2 * L70.layers == 160
    assert allreduce_seconds(H100, L70, 4, 133) * 1e3 == pytest.approx(1.16, abs=0.005)
    assert allreduce_seconds(H100, L70, 4, 8192) * 1e3 == pytest.approx(71.6, abs=0.05)
    assert allreduce_seconds(H100, L70, 4, 1, fixed_us=10) * 1e3 == pytest.approx(1.6, abs=0.01)
    assert allreduce_seconds(H100, L70, 1, 8192) == 0


def test_decode_step_on_tp4():
    assert group_step(H100, L70, "bf16", 4, [], 1, 2150) * 1e3 == pytest.approx(10.5, abs=0.05)
    assert group_step(H100, L70, "bf16", 4, [], 133, 2150) * 1e3 == pytest.approx(18.6, abs=0.05)


def test_prompt_chunks_fill_the_room():
    for prompt, room in [(2000, 3908), (500, 8192), (16000, 1000), (8192, 8192)]:
        assert sum(c for _, c in prompt_chunks(prompt, room)) == room


def test_kv_transfer_for_one_prompt():
    p = prefill_pool(H100, L70, "bf16", 4, 2000)
    assert p["kv_bytes"] == 655_360_000
    assert p["transfer"] * 1e3 == pytest.approx(0.36, abs=0.005)
    assert prefill_pool(H100, L70, "bf16", 4, 2000, "network")["transfer"] * 1e3 == pytest.approx(
        3.3, abs=0.05
    )
    assert p["latency"] * 1e3 == pytest.approx(
        367, abs=0.5
    )  # a full 8,192-token step: four prompts and a bit


def test_transfer_share_of_prefill_by_model():
    """Network seconds to ship a token's KV, over seconds of linear-layer math to compute it."""

    def share(m, link):
        return (kv_bytes_per_token(m) / link) / (2 * m.params / GPUS[H100].peak_flops)

    assert share(L70, nic_each_way()) == pytest.approx(0.046, abs=0.0005)
    assert share(L8, nic_each_way()) == pytest.approx(0.162, abs=0.0005)
    assert share(L70, nvlink_each_way(H100)) == pytest.approx(0.0051, abs=0.00005)


# ---- per-replica capacity and the planner ----
def test_colocated_vs_decode_only_replica():
    col = colocated(H100, L70, "bf16", 4, 2000, 300, 1.0, 0.1)
    assert (col["running"], col["budget"]) == (133, 1024)
    assert col["rate"] == pytest.approx(9.69, abs=0.005) and col["itl"] * 1e3 == pytest.approx(45.9, abs=0.05)
    dec = decode_pool(H100, L70, "bf16", 4, 2000, 300, 0.1)
    assert dec["running"] == 188 and dec["rate"] == pytest.approx(28.6, abs=0.05)
    assert dec["itl"] * 1e3 == pytest.approx(22.0, abs=0.05)
    assert prefill_pool(H100, L70, "bf16", 4, 2000)["rate"] == pytest.approx(11.17, abs=0.005)


def test_tp2_fits_one_request_and_is_useless():
    col = colocated(H100, L70, "bf16", 2, 2000, 300, 1.0, 0.1)
    assert col["running"] == 1 and col["rate"] == pytest.approx(0.16, abs=0.005)


def test_drill_1_chat_70b():
    rate = 2000 / 30  # 2,000 users, one message every 30 s each
    assert rate == pytest.approx(66.7, abs=0.05)
    bf = plan(H100, L70, "bf16", 2000, 300, 1.0, 0.1, rate)
    assert bf["colocated"]["tp"] == 4 and bf["colocated"]["colocated"]["replicas"] == 9
    assert bf["colocated"]["colocated"]["gpus"] == 36
    d = bf["disaggregated"]["disaggregated"]
    assert (bf["disaggregated"]["tp"], d["prefill_replicas"], d["decode_replicas"], d["gpus"]) == (
        4,
        8,
        3,
        44,
    )
    fp8 = plan(H100, L70, "fp8", 2000, 300, 1.0, 0.1, rate)
    assert fp8["colocated"]["tp"] == 2 and fp8["colocated"]["colocated"]["gpus"] == 18
    h200 = plan(H200, L70, "bf16", 2000, 300, 1.0, 0.1, rate)
    assert h200["colocated"]["tp"] == 2 and h200["colocated"]["colocated"]["gpus"] == 30


def test_drill_2_long_documents():
    p = plan(H100, L70, "fp8", 16000, 200, 3.0, 0.05, 10)
    assert p["colocated"]["tp"] == 2 and p["colocated"]["colocated"]["gpus"] == 22
    assert p["colocated"]["colocated"]["budget"] == 512
    d = p["disaggregated"]
    assert d["tp"] == 2 and d["disaggregated"]["gpus"] == 26
    net = plan(H100, L70, "fp8", 16000, 200, 3.0, 0.05, 10, link="network")["disaggregated"]
    assert net["disaggregated"]["prefill"]["transfer"] * 1e3 == pytest.approx(26.2, abs=0.05)


def test_drill_3_small_model():
    p = plan(H100, L8, "bf16", 500, 200, 0.5, 0.05, 100)
    assert p["colocated"]["tp"] == 1 and p["colocated"]["colocated"]["replicas"] == 2
    assert p["colocated"]["colocated"]["gpus"] == 2
    assert p["disaggregated"]["disaggregated"]["gpus"] == 3
    small = plan(H100, L8, "bf16", 500, 200, 0.5, 0.05, 20)
    assert (small["colocated"]["colocated"]["gpus"], small["disaggregated"]["disaggregated"]["gpus"]) == (
        1,
        2,
    )


def test_colocated_never_needs_more_gpus_in_this_model():
    for prompt, output, itl in [(500, 300, 0.03), (2000, 300, 0.05), (8000, 1000, 0.03), (16000, 200, 0.05)]:
        p = plan(H100, L70, "fp8", prompt, output, 2.0, itl, 50)
        assert p["colocated"]["colocated"]["gpus"] <= p["disaggregated"]["disaggregated"]["gpus"]


# ---- calculator spec and JS ----
def _spec():
    block = re.search(r'<div class="ts-capcalc".*?<script type="application/json">(.*?)</script>', BODY, re.S)
    return json.loads(block.group(1))


def test_calculator_figures_match_python():
    spec = _spec()
    for g in spec["gpus"]:
        py = GPUS[g["id"]]
        assert (
            g["tflops"] * 1e12 == py.peak_flops
            and g["tbps"] * 1e12 == py.bandwidth
            and g["gb"] == py.memory_gb
        )
        assert g["fp8_tflops"] == FP8_SPARSE[g["id"]] / 2
        assert g["nvlink_each_way"] * 1e9 == nvlink_each_way(g["id"])
    for m in spec["models"]:
        py = MODELS[m["id"]]
        assert (m["layers"], m["q_heads"], m["kv_heads"], m["head_dim"]) == (
            py.layers, py.q_heads, py.kv_heads, py.head_dim)  # fmt: skip
        assert m["params"] * 1e9 == py.params
    links = {x["id"]: x["each_way"] * 1e9 for x in spec["links"]}
    assert links == {"nvlink": 450e9, "network": nic_each_way()}
    assert {d["id"]: d["bytes"] for d in spec["dtypes"]} == {"bf16": 2, "fp8": 1}


def _js_function(name: str) -> str:
    m = re.search(rf"  function {name}\(.*?\n  }}\n", UI_JS, re.S)
    assert m, name
    return m.group(0)


JS_FUNCS = [
    "capAllReduce",
    "capStep",
    "capFit",
    "capChunks",
    "capColocated",
    "capDecode",
    "capPrefill",
    "capPlan",
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize(
    "gpu,model,dtype,prompt,output,ttft,itl,rate,link,fixed",
    [(H100, "llama-3.1-70b", "bf16", 2000, 300, 1.0, 0.1, 2000 / 30, "nvlink", 0.0),
     (H100, "llama-3.1-70b", "fp8", 16000, 200, 3.0, 0.05, 10, "network", 0.0),
     (H200, "llama-3.1-70b", "bf16", 2000, 300, 1.0, 0.1, 40, "nvlink", 10.0),
     (H100, "llama-3.1-8b", "bf16", 500, 200, 0.5, 0.05, 100, "nvlink", 0.0),
     (H200, "llama-3.1-8b", "fp8", 8000, 1000, 2.0, 0.03, 25, "network", 5.0)],
)  # fmt: skip
def test_calculator_js_matches_python(gpu, model, dtype, prompt, output, ttft, itl, rate, link, fixed):
    spec = _spec()
    g = next(x for x in spec["gpus"] if x["id"] == gpu)
    m = next(x for x in spec["models"] if x["id"] == model)
    d = next(x for x in spec["dtypes"] if x["id"] == dtype)
    lk = next(x for x in spec["links"] if x["id"] == link)
    x = {"prompt": prompt, "output": output, "ttft": ttft, "itl": itl, "rate": rate, "headroom": 0.8,
         "fixed_us": fixed, "util": 0.92, "reserve": 3}  # fmt: skip
    src = "".join(_js_function(f) for f in JS_FUNCS)
    src += f"console.log(JSON.stringify(capPlan({json.dumps(g)}, {json.dumps(m)}, {json.dumps(d)}, "
    src += f"{json.dumps(lk)}, {json.dumps(x)}, [1, 2, 4, 8])));"
    js = json.loads(subprocess.run(["node", "-e", src], capture_output=True, text=True, check=True).stdout)
    py = plan(gpu, MODELS[model], dtype, prompt, output, ttft, itl, rate, link=link, fixed_us=fixed)
    assert [r["tp"] for r in js["rows"]] == [r["tp"] for r in py["rows"]]
    for jr, pr in zip(js["rows"], py["rows"], strict=True):
        assert jr["fit"] == fit(gpu, MODELS[model], dtype, pr["tp"], prompt + output)
        for kind in ("colocated", "disaggregated"):
            assert (jr[kind] is None) == (pr[kind] is None)
            if pr[kind]:
                assert jr[kind]["gpus"] == pr[kind]["gpus"]
        if pr["colocated"]:
            c, pc = jr["colocated"], pr["colocated"]
            assert (c["running"], c["budget"]) == (pc["running"], pc["budget"])
            assert c["rate"] == pytest.approx(pc["rate"], rel=1e-9) and c["itl"] == pytest.approx(
                pc["itl"], rel=1e-9
            )
        if pr["disaggregated"]:
            assert jr["disaggregated"]["ttft"] == pytest.approx(pr["disaggregated"]["ttft"], rel=1e-9)
    for kind in ("colocated", "disaggregated"):
        assert (js[kind] or {}).get("tp") == (py[kind] or {}).get("tp")


def test_cli_prints_both_designs():
    out = subprocess.run(
        [sys.executable, "plan.py", "h100-sxm", "llama-3.1-70b", "bf16", "2000", "300", "1.0", "0.1", "66.7"],
        cwd=HERE, capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert "colocated: TP=4, 36 GPUs" in out and "disaggregated: TP=4, 44 GPUs" in out


def test_tp_cli():
    out = subprocess.run(
        [sys.executable, "tp.py", "h100-sxm", "llama-3.1-70b", "bf16", "2000", "300"],
        cwd=HERE, capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert "TP=4: KV budget  142.4 GB,   188 requests" in out and "Smallest TP that fits: 2" in out
    assert math.isclose(66.7, 2000 / 30, abs_tol=0.05)


def test_smaller_page_figures():
    assert GPUS[H100].memory_gb * 8 == 640  # part 4: an 800 GB model is too big for one node
    assert nic_each_way() / nvlink_each_way(H100) == pytest.approx(1 / 9)
    assert 16000 * kv_bytes_per_token(L70, 1) / 1e9 == pytest.approx(2.6, abs=0.05)  # drill 2, FP8 cache
    d = plan(H100, L70, "fp8", 16000, 200, 3.0, 0.05, 10)
    premium = d["disaggregated"]["disaggregated"]["gpus"] / d["colocated"]["colocated"]["gpus"] - 1
    assert premium == pytest.approx(0.18, abs=0.005)  # drill 2, split premium
    col = plan(H100, L70, "bf16", 2000, 300, 1.0, 0.1, 2000 / 30)["colocated"]["colocated"]
    assert col["rate"] == pytest.approx(9.7, abs=0.05)
    assert 5 * 8 - col["gpus"] == 4  # five nodes leave room for one spare TP=4 replica
    tp2 = plan(H100, L70, "bf16", 2000, 300, 1.0, 0.1, 2000 / 30, sizes=(2,))["colocated"]["colocated"]
    assert tp2["replicas"] > 100  # "hundreds of replicas"
    p = plan(H100, L70, "fp8", 16000, 200, 3.0, 0.05, 10)["colocated"]["colocated"]
    assert p["rate"] == pytest.approx(1.2, abs=0.05)

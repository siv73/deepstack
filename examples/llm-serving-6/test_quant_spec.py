"""Every number the Part 6 page quotes from quant.py, spec.py and the calculator."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from gpus import GPUS
from kv_cache import kv_bytes_per_token
from models import MODELS
from precision import FP8_SPARSE, INT8_SPARSE
from quant import crossover_batch, decode, kv_budget, max_requests, weight_bytes
from spec import draft_acceptance_rate, paper_speedup, served, tokens_per_round

HERE = Path(__file__).parent
BODY = (HERE.parent.parent / "content" / "llm-serving-6" / "body.html").read_text()
UI_JS = (HERE.parent.parent / "ui" / "ts.js").read_text()
H100, H200 = GPUS["h100-sxm"], GPUS["h200-sxm"]
L8, L70 = MODELS["llama-3.1-8b"], MODELS["llama-3.1-70b"]


@pytest.mark.parametrize("name", ["gpus.py", "estimate.py", "models.py", "kv_cache.py"])
def test_part2_estimator_is_copied_unchanged(name):
    assert (HERE / name).read_text() == (HERE.parent / "llm-serving-2" / name).read_text()


# ---- bytes per parameter ----
def test_weight_bytes():
    assert [weight_bytes(L8, s) / 1e9 for s in ("bf16", "fp8", "int8", "int4")] == [16, 8, 8, 4]
    assert [weight_bytes(L70, s) / 1e9 for s in ("bf16", "fp8", "int4")] == [140, 70, 35]
    assert (weight_bytes(L8, "bf16") - weight_bytes(L8, "int4")) / 1e9 == 12  # choosing quiz


def test_kv_bytes_per_token_halves():
    assert kv_bytes_per_token(L8, 2) == 131_072
    assert kv_bytes_per_token(L8, 1) == 65_536


# ---- capacity table (8B, H100, 8,192 tokens) ----
def test_h100_capacity_table():
    assert kv_budget(H100, L8, "bf16") == pytest.approx(54.6e9)
    assert kv_budget(H100, L8, "fp8") == pytest.approx(62.6e9)
    assert kv_budget(H100, L8, "int4") == pytest.approx(66.6e9)
    assert max_requests(H100, L8, "bf16", "bf16", 8192) == 50
    assert max_requests(H100, L8, "bf16", "fp8", 8192) == 101
    assert max_requests(H100, L8, "fp8", "fp8", 8192) == 116
    assert max_requests(H100, L8, "int4", "fp8", 8192) == 124


def test_h200_predict():
    assert max_requests(H200, L8, "bf16", "bf16", 8192) == 103
    assert max_requests(H200, L8, "bf16", "fp8", 8192) == 206
    assert max_requests(H200, L8, "fp8", "fp8", 8192) == 221


def test_70b_fit():
    assert kv_budget(H100, L70, "bf16") < 0
    assert kv_budget(H100, L70, "fp8") == pytest.approx(0.6e9)
    assert max_requests(H100, L70, "fp8", "fp8", 4096) == 0
    assert kv_budget(H100, L70, "int4") == pytest.approx(35.6e9)
    assert max_requests(H100, L70, "int4", "fp8", 4096) == 53
    assert max_requests(H200, L70, "fp8", "fp8", 4096) == 84


# ---- decode speed ----
def test_batch1_bf16_is_about_200_tokens_per_s():
    d = decode("h100-sxm", L8, "bf16", "bf16", 1, 4096)
    assert d["bound"] == "memory" and d["tokens_per_s"] == pytest.approx(203, abs=1)


def test_calculator_opening_question():
    assert decode("h100-sxm", L8, "bf16", "bf16", 32, 4096)["tokens_per_s"] == pytest.approx(3231, abs=1)
    assert decode("h100-sxm", L8, "fp8", "fp8", 32, 4096)["tokens_per_s"] == pytest.approx(6462, abs=1)
    assert served("h100-sxm", L8, "fp8", "fp8", 32, 4096, 4, 0.7, 0.05)["tokens_per_s"] == pytest.approx(
        14_933, abs=1
    )


def test_crossover_batches():
    assert crossover_batch("h100-sxm", L8, "bf16") == 296  # Part 1's number
    assert crossover_batch("h100-sxm", L8, "fp8") == 296
    assert crossover_batch("h100-sxm", L8, "int4") == 74
    assert crossover_batch("a100-pcie", L8, "bf16") == 162
    assert crossover_batch("a100-pcie", L8, "fp8") == 81  # no FP8 Tensor Cores: weight-only
    assert decode("a100-pcie", L8, "fp8", "fp8", 1, 1000)["math"] == "bf16"


def test_int4_edge_fades_with_batch():
    f1, i1 = (decode("h100-sxm", L8, s, "fp8", 1, 1000)["tokens_per_s"] for s in ("fp8", "int4"))
    assert (round(f1), round(i1)) == (415, 824)
    f400, i400 = (decode("h100-sxm", L8, s, "fp8", 400, 1000)["tokens_per_s"] for s in ("fp8", "int4"))
    assert i400 / f400 == pytest.approx(1.13, abs=0.005)
    assert max_requests(H100, L8, "int4", "fp8", 1000) >= 400


# ---- speculation arithmetic ----
def test_tokens_per_round_bounds():
    assert tokens_per_round(4, 0.0) == 1
    assert tokens_per_round(4, 1.0) == 5


def test_worked_example():
    assert tokens_per_round(4, 0.7) == pytest.approx(2.77, abs=0.005)
    assert paper_speedup(4, 0.7, 0.05) == pytest.approx(2.3, abs=0.02)
    assert draft_acceptance_rate(4, 0.7) == pytest.approx(0.44, abs=0.005)


def test_speculation_at_low_and_high_batch():
    low = served("h100-sxm", L8, "bf16", "bf16", 1, 500, 4, 0.5, 0.05)
    high = served("h100-sxm", L8, "bf16", "bf16", 256, 500, 4, 0.5, 0.05)
    assert low["speedup"] == pytest.approx(1.61, abs=0.005) and low["verify_bound"] == "memory"
    assert high["speedup"] == pytest.approx(0.82, abs=0.005) and high["verify_bound"] == "compute"
    assert 256 * (4 + 1) == 1280
    assert max_requests(H100, L8, "bf16", "bf16", 500) >= 256


def test_itl_and_tpot_diverge():
    r = served("h100-sxm", L8, "bf16", "bf16", 1, 1000, 4, 0.7, 0.05)
    assert r["tpot_s"] == pytest.approx(0.0021, abs=5e-5)
    assert r["gap_s"] == pytest.approx(0.0058, abs=5e-5)


# ---- calculator spec and JS ----
def _spec():
    block = re.search(
        r'<div class="ts-quantcalc".*?<script type="application/json">(.*?)</script>', BODY, re.S
    )
    return json.loads(block.group(1))


def test_calculator_hardware_matches_python():
    spec = _spec()
    for g in spec["gpus"]:
        py = GPUS[g["id"]]
        assert (
            g["tflops"] * 1e12 == py.peak_flops
            and g["tbps"] * 1e12 == py.bandwidth
            and g["gb"] == py.memory_gb
        )
        fp8 = FP8_SPARSE[g["id"]]
        assert g["fp8_tflops"] == (None if fp8 is None else fp8 / 2)
        assert g["int8_tops"] == INT8_SPARSE[g["id"]] / 2
    for m in spec["models"]:
        py = MODELS[m["id"]]
        assert (m["layers"], m["q_heads"], m["kv_heads"], m["head_dim"]) == (
            py.layers, py.q_heads, py.kv_heads, py.head_dim)  # fmt: skip
        assert m["params"] * 1e9 == py.params


def _js_function(name: str) -> str:
    m = re.search(rf"  function {name}\(.*?\n  }}\n", UI_JS, re.S)
    assert m, name
    return m.group(0)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize(
    "gpu,model,scheme,kv,batch,ctx,k,alpha",
    [("h100-sxm", "llama-3.1-8b", "fp8", "fp8", 32, 4096, 4, 0.7),
     ("h100-sxm", "llama-3.1-8b", "bf16", "bf16", 256, 500, 4, 0.5),
     ("a100-pcie", "llama-3.1-8b", "fp8", "bf16", 8, 2000, 3, 0.6),
     ("h200-sxm", "llama-3.1-70b", "int4", "fp8", 64, 4096, 5, 0.8),
     ("h100-nvl", "llama-3.1-8b", "int8", "fp8", 128, 1000, 2, 1.0)],
)  # fmt: skip
def test_calculator_js_matches_python(gpu, model, scheme, kv, batch, ctx, k, alpha):
    spec = _spec()
    g = next(x for x in spec["gpus"] if x["id"] == gpu)
    m = next(x for x in spec["models"] if x["id"] == model)
    s = next(x for x in spec["schemes"] if x["id"] == scheme)
    kvd = next(x for x in spec["kv"] if x["id"] == kv)
    x = {"batch": batch, "context": ctx, "k": k, "alpha": alpha, "c": 0.05, "util": 0.92, "reserve": 3}
    src = _js_function("quantStep") + _js_function("quantEstimate")
    src += f"console.log(JSON.stringify(quantEstimate({json.dumps(g)}, {json.dumps(m)}, {json.dumps(s)}, "
    src += f"{json.dumps(kvd)}, {json.dumps(x)})));"
    js = json.loads(subprocess.run(["node", "-e", src], capture_output=True, text=True, check=True).stdout)
    py_m = MODELS[model]
    assert js["fit"] == max_requests(GPUS[gpu], py_m, scheme, kv, ctx)
    assert js["tokensPerS"] == pytest.approx(
        decode(gpu, py_m, scheme, kv, batch, ctx)["tokens_per_s"], rel=1e-9
    )
    py = served(gpu, py_m, scheme, kv, batch, ctx, k, alpha, 0.05)
    assert js["e"] == pytest.approx(tokens_per_round(k, alpha), rel=1e-9)
    assert js["speedup"] == pytest.approx(py["speedup"], rel=1e-9)
    assert js["tpot"] == pytest.approx(py["tpot_s"], rel=1e-9)
    assert js["gap"] == pytest.approx(py["gap_s"], rel=1e-9)


def test_cli_prints_fit_and_decode():
    out = subprocess.run(
        [sys.executable, "quant.py", "h100-sxm", "llama-3.1-8b", "fp8", "fp8", "8192", "32"],
        cwd=HERE, capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert "Requests of 8,192 tokens that fit: 116" in out and "memory-bound" in out

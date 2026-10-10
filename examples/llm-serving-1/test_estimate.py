"""Every number the page quotes from estimate.py and gpus.py."""

import subprocess
import sys
from pathlib import Path

import pytest
from estimate import estimate, forward_pass
from gpus import GPUS

H100 = GPUS["h100-sxm"]
EIGHT_B = 8e9


def test_dense_peak_is_half_the_sparsity_figure():
    assert H100.peak_flops == pytest.approx(989.5e12)


def test_h100_ridge_point_is_about_295_flops_per_byte():
    assert estimate(H100, EIGHT_B, 2000, 300)["ridge_flops_per_byte"] == pytest.approx(295.4, abs=0.1)


def test_8b_on_h100_batch_1():
    r = estimate(H100, EIGHT_B, 2000, 300)
    assert r["fits"]
    assert r["prefill_bound"] == "compute"
    assert r["ttft_s"] == pytest.approx(0.0323, abs=1e-4)  # about 32 ms
    assert r["decode_bound"] == "memory"
    assert r["tpot_s"] == pytest.approx(0.00478, abs=1e-5)  # about 4.8 ms
    assert r["decode_tokens_per_s"] == pytest.approx(209, abs=1)
    assert r["e2e_s"] == pytest.approx(1.46, abs=0.01)


def test_decode_uses_about_a_third_of_a_percent_of_compute_at_batch_1():
    r = estimate(H100, EIGHT_B, 2000, 300)
    compute_s = 2 * EIGHT_B / H100.peak_flops
    assert compute_s / r["tpot_s"] == pytest.approx(0.0034, abs=1e-4)


def test_decode_intensity_equals_batch_so_it_crosses_the_ridge_near_296():
    assert forward_pass(H100, EIGHT_B, 295)[1] == "memory"
    assert forward_pass(H100, EIGHT_B, 296)[1] == "compute"


def test_batching_decode_multiplies_throughput_while_memory_bound():
    one = estimate(H100, EIGHT_B, 2000, 300, batch=1)
    many = estimate(H100, EIGHT_B, 2000, 300, batch=256)
    assert many["tpot_s"] == one["tpot_s"]  # same weight read, shared by 256 requests
    assert many["decode_tokens_per_s"] == pytest.approx(256 * one["decode_tokens_per_s"])


def test_short_prompts_are_memory_bound_long_ones_compute_bound():
    assert forward_pass(H100, EIGHT_B, 200)[1] == "memory"
    assert forward_pass(H100, EIGHT_B, 2000)[1] == "compute"


def test_70b_in_bf16_does_not_fit_on_one_h100_but_fits_an_h200():
    assert not estimate(H100, 70e9, 2000, 300)["fits"]  # 140 GB of weights > 80 GB
    assert estimate(GPUS["h200-sxm"], 70e9, 2000, 300)["fits"]  # 140 GB <= 141 GB


def test_h200_decodes_faster_than_h100_with_the_same_compute():
    h100, h200 = estimate(H100, EIGHT_B, 2000, 300), estimate(GPUS["h200-sxm"], EIGHT_B, 2000, 300)
    assert h200["ttft_s"] == h100["ttft_s"]  # prefill is compute-bound, same FLOPs
    assert h200["tpot_s"] == pytest.approx(h100["tpot_s"] * 3.35 / 4.8)  # bandwidth ratio
    assert h200["decode_tokens_per_s"] == pytest.approx(300, abs=1)


def test_cli_prints_the_estimate():
    here = Path(__file__).parent
    out = subprocess.run(
        [sys.executable, str(here / "estimate.py"), "h100-sxm", "8", "2000", "300"],
        capture_output=True,
        text=True,
        check=True,
        cwd=here,
    ).stdout
    assert "decode_bound: memory" in out
    assert "decode_tokens_per_s: 209.4" in out

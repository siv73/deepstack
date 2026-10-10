"""Every number the page quotes from kv_cache.py, models.py and the copied Part 1 estimator."""

import subprocess
import sys
from pathlib import Path

import pytest
from gpus import GPUS
from kv_cache import (
    crossover_batch,
    decode_step,
    generation_seconds,
    kv_bytes_per_token,
    max_requests,
)
from models import MODELS

HERE = Path(__file__).parent
H100, H200 = GPUS["h100-sxm"], GPUS["h200-sxm"]
L8, L70 = MODELS["llama-3.1-8b"], MODELS["llama-3.1-70b"]
MHA, MQA = MODELS["8b-as-mha"], MODELS["8b-as-mqa"]


@pytest.mark.parametrize("name", ["gpus.py", "estimate.py"])
def test_part1_estimator_is_copied_unchanged(name):
    assert (HERE / name).read_text() == (HERE.parent / "llm-serving-1" / name).read_text()


def test_llama_shapes_and_group_sizes():
    assert (L8.layers, L8.q_heads, L8.kv_heads, L8.head_dim, L8.group_size) == (32, 32, 8, 128, 4)
    assert (L70.layers, L70.q_heads, L70.kv_heads, L70.head_dim, L70.group_size) == (80, 64, 8, 128, 8)


def test_kv_bytes_per_token():
    assert kv_bytes_per_token(L8) == 131_072  # 128 KiB
    assert kv_bytes_per_token(L70) == 327_680  # 320 KiB
    assert kv_bytes_per_token(MHA) == 524_288 == 4 * kv_bytes_per_token(L8)
    assert kv_bytes_per_token(MQA) == 16_384 == kv_bytes_per_token(L8) // 8
    assert kv_bytes_per_token(L8, dtype_bytes=1) == 65_536  # an 8-bit cache halves it
    quiz_model = MODELS["llama-3.1-8b"].__class__("quiz", 0, layers=48, q_heads=32, kv_heads=8, head_dim=128)
    assert kv_bytes_per_token(quiz_model) == 196_608


def test_kv_bytes_per_request():
    assert 8192 * kv_bytes_per_token(L8) == 2**30  # about 1.07 GB
    assert 8192 * kv_bytes_per_token(L70) == pytest.approx(2.68e9, abs=0.005e9)
    assert 131_072 * kv_bytes_per_token(L8) == pytest.approx(17.2e9, abs=0.05e9)  # one full 128K context
    assert 2300 * kv_bytes_per_token(L8) == pytest.approx(301.5e6, rel=1e-3)


def test_h100_kv_budget_and_capacity_for_8b():
    budget = 80e9 * 0.92 - 16e9 - 3e9
    assert budget == pytest.approx(54.6e9)
    assert budget / kv_bytes_per_token(L8) == pytest.approx(416_565, abs=1)
    assert max_requests(H100, L8, 2300) == 181
    assert max_requests(H100, L8, 4096) == 101
    assert max_requests(H100, L8, 8192) == 50
    assert max_requests(H100, L8, 131_072) == 3


def test_h200_roughly_doubles_8k_capacity():
    assert max_requests(H200, L8, 8192) == 103
    h200_budget = 141e9 * 0.92 - 16e9 - 3e9
    assert h200_budget == pytest.approx(110.72e9)
    assert h200_budget / 54.6e9 == pytest.approx(2.03, abs=0.005)


def test_head_sharing_changes_how_many_fit():
    assert max_requests(H100, MHA, 8192) == 12
    assert max_requests(H100, MQA, 8192) == 406


def test_70b_does_not_fit_one_h100_or_h200():
    assert max_requests(H100, L70, 8192) == 0
    assert max_requests(H200, L70, 8192) == 0  # 140 GB of weights > 0.92 x 141 GB


def test_kv_reads_at_batch_1_add_about_two_percent():
    step = decode_step(H100, L8, 1, 2300)
    assert step["bound"] == "memory"
    assert step["kv_share_of_reads"] == pytest.approx(0.0185, abs=1e-4)
    assert step["seconds"] == pytest.approx(0.00487, abs=1e-5)


def test_64_requests_at_2000_tokens_read_as_much_kv_as_weights():
    step = decode_step(H100, L8, 64, 2000)
    assert step["bound"] == "memory"
    assert step["kv_share_of_reads"] == pytest.approx(0.51, abs=0.005)
    assert step["seconds"] == pytest.approx(0.00978, abs=1e-5)  # Part 1 weights-only: 4.78 ms
    assert step["tokens_per_s"] == pytest.approx(6541, abs=1)  # Part 1 weights-only: about 13,400
    assert step["flops_per_byte"] == pytest.approx(33.3, abs=0.05)


def test_full_h100_at_2300_tokens_is_still_deeply_memory_bound():
    step = decode_step(H100, L8, 181, 2300)
    assert step["bound"] == "memory"
    assert step["flops_per_byte"] == pytest.approx(44.1, abs=0.05)
    assert step["kv_share_of_reads"] == pytest.approx(0.77, abs=0.005)
    assert step["seconds"] == pytest.approx(0.0211, abs=1e-4)
    assert step["tokens_per_s"] == pytest.approx(8593, abs=1)


def test_crossover_batch_moves_right_with_context_then_disappears():
    assert crossover_batch(H100, L8, 0) == 296  # Part 1's weights-only crossover
    assert crossover_batch(H100, L8, 200) == 566
    assert crossover_batch(H100, L8, 418) is not None
    assert crossover_batch(H100, L8, 419) is None
    assert crossover_batch(H100, L8, 2000) is None
    assert crossover_batch(H100, L8, 8192) is None


def test_bigger_groups_raise_attention_intensity():
    assert crossover_batch(H100, MQA, 2000) == 642  # MQA: 32 FLOPs per KV byte
    assert max_requests(H100, MQA, 2000) >= 642  # and that many fit
    assert crossover_batch(H100, MHA, 100) == 8345  # MHA: 1 FLOP per KV byte


def test_without_a_cache_work_grows_with_the_square_of_output_length():
    with_cache_tokens = 2000 + 300 - 1
    without_cache_tokens = sum(2000 + k for k in range(300))
    assert (with_cache_tokens, without_cache_tokens) == (2299, 644_850)
    assert without_cache_tokens / with_cache_tokens == pytest.approx(280, abs=1)
    assert generation_seconds(H100, L8, 2000, 300) == pytest.approx(1.46, abs=0.01)
    assert generation_seconds(H100, L8, 2000, 300, cache=False) == pytest.approx(10.4, abs=0.05)
    assert generation_seconds(H100, L8, 2000, 2000) == pytest.approx(9.6, abs=0.05)
    assert generation_seconds(H100, L8, 2000, 2000, cache=False) == pytest.approx(97, abs=0.5)


def test_cli_prints_capacity_and_crossover():
    out = subprocess.run(
        [sys.executable, str(HERE / "kv_cache.py"), "h100-sxm", "llama-3.1-8b", "8192"],
        capture_output=True,
        text=True,
        check=True,
        cwd=HERE,
    ).stdout
    assert "KV per token: 131,072 bytes" in out
    assert "Requests that fit at 8,192 tokens: 50" in out
    assert "memory-bound" in out
    assert "Compute-bound from batch: never" in out


def test_decode_table_kv_bytes_and_batch_1_speed():
    assert 2300 * kv_bytes_per_token(L8) / 1e9 == pytest.approx(0.30, abs=0.005)
    assert 64 * 2000 * kv_bytes_per_token(L8) / 1e9 == pytest.approx(16.8, abs=0.05)
    assert 181 * 2300 * kv_bytes_per_token(L8) / 1e9 == pytest.approx(54.6, abs=0.05)
    assert decode_step(H100, L8, 1, 2300)["tokens_per_s"] == pytest.approx(206, abs=1)


def test_attention_alone_does_group_size_flops_per_kv_byte():
    attn_flops_per_cached_token = 4 * L8.layers * L8.q_heads * L8.head_dim
    assert attn_flops_per_cached_token == 524_288
    assert attn_flops_per_cached_token / kv_bytes_per_token(L8) == L8.group_size == 4


def test_intensity_ceiling_as_batch_grows_without_limit():
    assert decode_step(H100, L8, 10**9, 2000)["flops_per_byte"] == pytest.approx(65.0, abs=0.1)
    assert decode_step(H100, L8, 10**9, 8192)["flops_per_byte"] == pytest.approx(18.9, abs=0.1)
    assert crossover_batch(H100, L8, 418) == 130_477


def test_drill_200_chats_at_4k_tokens_needs_two_h100s():
    assert max_requests(H100, L8, 4096) == 101  # so 200 chats need 2 GPUs
    step = decode_step(H100, L8, 101, 4096)
    assert step["bound"] == "memory"
    assert step["seconds"] == pytest.approx(0.021, abs=5e-4)
    assert step["tokens_per_s"] == pytest.approx(4818, abs=1)


def test_drill_doubling_batch_at_6000_tokens():
    assert max_requests(H100, L8, 6000) == 69
    small, big = decode_step(H100, L8, 32, 6000), decode_step(H100, L8, 64, 6000)
    assert small["seconds"] == pytest.approx(0.0123, abs=1e-4)
    assert big["seconds"] == pytest.approx(0.0198, abs=1e-4)
    assert big["seconds"] / small["seconds"] == pytest.approx(1.61, abs=0.01)
    assert big["tokens_per_s"] / small["tokens_per_s"] == pytest.approx(1.24, abs=0.01)


def test_raising_utilization_to_095_adds_three_8k_requests():
    assert max_requests(H100, L8, 8192, util=0.95) == 53


def test_capping_context_near_p99_nearly_triples_capacity():
    assert max_requests(H100, L8, 3000) == 138
    assert 80e9 * (0.99 - 0.92) / (8192 * kv_bytes_per_token(L8)) == pytest.approx(5.2, abs=0.05)
    assert 50 * 8192 * kv_bytes_per_token(L8) / 1e9 == pytest.approx(53.7, abs=0.05)
    assert decode_step(H100, L8, 50, 8192)["kv_share_of_reads"] == pytest.approx(0.77, abs=0.005)

"""KV cache size, how many requests fit, and decode step time including KV reads.

Extends Part 1's weights-only estimator. Usage: uv run kv_cache.py h100-sxm llama-3.1-8b 8192
"""

import math
import sys

from estimate import BYTES_PER_PARAM, forward_pass
from gpus import GPU, GPUS
from models import MODELS, Model

BF16 = 2  # bytes per stored K or V value


def kv_bytes_per_token(m: Model, dtype_bytes: int = BF16) -> int:
    return 2 * m.layers * m.kv_heads * m.head_dim * dtype_bytes  # K and V, every layer, every KV head


def max_requests(gpu: GPU, m: Model, context: int, util: float = 0.92, reserve_gb: float = 3.0) -> int:
    """Requests of `context` tokens whose KV cache fits in what is left after weights and reserve."""
    budget = gpu.memory_gb * 1e9 * util - m.params * BYTES_PER_PARAM - reserve_gb * 1e9
    return max(0, math.floor(budget / (context * kv_bytes_per_token(m))))


def decode_step(gpu: GPU, m: Model, batch: int, context: int) -> dict:
    """One decode step for `batch` requests, each attending over `context` cached tokens."""
    attn_flops = 4 * m.layers * m.q_heads * m.head_dim * context  # q·K and scores·V, multiply + add
    flops = batch * (2 * m.params + attn_flops)
    weight_bytes, kv_bytes = m.params * BYTES_PER_PARAM, batch * context * kv_bytes_per_token(m)
    compute_s, memory_s = flops / gpu.peak_flops, (weight_bytes + kv_bytes) / gpu.bandwidth
    return {
        "seconds": max(compute_s, memory_s),
        "bound": "compute" if compute_s > memory_s else "memory",
        "flops_per_byte": flops / (weight_bytes + kv_bytes),
        "kv_share_of_reads": kv_bytes / (weight_bytes + kv_bytes),
        "tokens_per_s": batch / max(compute_s, memory_s),
    }


def crossover_batch(gpu: GPU, m: Model, context: int) -> int | None:
    """Smallest batch at which decode turns compute-bound, or None if no batch size gets there."""
    ridge = gpu.peak_flops / gpu.bandwidth
    per_req_flops = 2 * m.params + 4 * m.layers * m.q_heads * m.head_dim * context
    per_req_bytes = context * kv_bytes_per_token(m)
    if per_req_flops <= ridge * per_req_bytes:
        return None  # each extra request adds reads at least as fast as it adds arithmetic
    return math.ceil(ridge * m.params * BYTES_PER_PARAM / (per_req_flops - ridge * per_req_bytes))


def generation_seconds(gpu: GPU, m: Model, prompt: int, output: int, cache: bool = True) -> float:
    """Weights-only time to produce `output` tokens; without a cache every step reprocesses everything."""
    if cache:
        return forward_pass(gpu, m.params, prompt)[0] + (output - 1) * forward_pass(gpu, m.params, 1)[0]
    return sum(forward_pass(gpu, m.params, prompt + k)[0] for k in range(output))


if __name__ == "__main__":
    gpu, m, context = GPUS[sys.argv[1]], MODELS[sys.argv[2]], int(sys.argv[3])
    n = max_requests(gpu, m, context)
    print(f"KV per token: {kv_bytes_per_token(m):,} bytes; per request: {context * kv_bytes_per_token(m):,}")
    print(f"Requests that fit at {context:,} tokens: {n}")
    step = decode_step(gpu, m, max(n, 1), context)
    print(
        f"Decode at {max(n, 1)} requests: {step['seconds'] * 1e3:.2f} ms, {step['bound']}-bound, "
        f"{step['flops_per_byte']:.1f} FLOPs/byte, {step['tokens_per_s']:,.0f} tokens/s"
    )
    print(f"Compute-bound from batch: {crossover_batch(gpu, m, context) or 'never'}")

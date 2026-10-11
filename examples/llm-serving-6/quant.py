"""Part 2's KV estimator with a weight scheme and a KV data type.

Weights: bytes per parameter from the scheme; the linear layers' FLOPs run at the
scheme's multiply precision. Attention over the cache stays at the BF16 rate.
Every parameter is treated as quantized (real checkpoints keep some layers in 16 bits).
Usage: uv run quant.py h100-sxm llama-3.1-8b fp8 fp8 8192 32
"""

import math
import sys

from gpus import GPU, GPUS
from kv_cache import kv_bytes_per_token
from models import MODELS, Model
from precision import BYTES, SCHEMES, dense_ops


def weight_bytes(m: Model, scheme: str) -> float:
    return m.params * BYTES[SCHEMES[scheme].weight]


def kv_budget(gpu: GPU, m: Model, scheme: str, util: float = 0.92, reserve_gb: float = 3.0) -> float:
    return gpu.memory_gb * 1e9 * util - weight_bytes(m, scheme) - reserve_gb * 1e9


def max_requests(gpu: GPU, m: Model, scheme: str, kv: str, context: int) -> int:
    per_request = context * kv_bytes_per_token(m, int(BYTES[kv]))
    return max(0, math.floor(kv_budget(gpu, m, scheme) / per_request))


def step_seconds(gpu_id: str, m: Model, scheme: str, kv: str, batch: int, context: int, tokens: int = 1):
    """One forward pass: `batch` requests, `tokens` new positions each, over `context` cached tokens."""
    gpu = GPUS[gpu_id]
    lin_peak, math_used = dense_ops(gpu_id, gpu.peak_flops, SCHEMES[scheme].math)
    lin_s = batch * tokens * 2 * m.params / lin_peak
    attn_s = batch * tokens * 4 * m.layers * m.q_heads * m.head_dim * context / gpu.peak_flops
    reads = weight_bytes(m, scheme) + batch * context * kv_bytes_per_token(m, int(BYTES[kv]))
    mem_s = reads / gpu.bandwidth
    compute_s = lin_s + attn_s
    return max(compute_s, mem_s), ("compute" if compute_s > mem_s else "memory"), math_used


def decode(gpu_id: str, m: Model, scheme: str, kv: str, batch: int, context: int) -> dict:
    s, bound, math_used = step_seconds(gpu_id, m, scheme, kv, batch, context)
    return {"seconds": s, "bound": bound, "math": math_used, "tokens_per_s": batch / s}


def crossover_batch(gpu_id: str, m: Model, scheme: str) -> int:
    """Weights only (no KV reads): the batch at which a decode step turns compute-bound."""
    lin_peak, _ = dense_ops(gpu_id, GPUS[gpu_id].peak_flops, SCHEMES[scheme].math)
    return math.ceil(lin_peak * weight_bytes(m, scheme) / GPUS[gpu_id].bandwidth / (2 * m.params))


if __name__ == "__main__":
    gpu_id, model_id, scheme, kv = sys.argv[1:5]
    context, batch = int(sys.argv[5]), int(sys.argv[6])
    m, gpu = MODELS[model_id], GPUS[gpu_id]
    print(
        f"Weights: {weight_bytes(m, scheme) / 1e9:.1f} GB; KV budget {kv_budget(gpu, m, scheme) / 1e9:.1f} GB"
    )
    print(f"Requests of {context:,} tokens that fit: {max_requests(gpu, m, scheme, kv, context)}")
    d = decode(gpu_id, m, scheme, kv, batch, context)
    print(f"Decode at batch {batch}: {d['seconds'] * 1e3:.2f} ms, {d['bound']}-bound, ", end="")
    print(f"{d['tokens_per_s']:,.0f} tokens/s")

"""Time for one forward pass (one engine step) that mixes prefills and decodes.

Part 2's model, generalised: a step reads the weights once, plus the KV cache of every
decoding request, and does 2 FLOPs per parameter per token plus attention over the cache.
Best case: 100% of peak, BF16 weights, KV writes and activations left out.
"""

from gpus import GPU
from kv_cache import kv_bytes_per_token
from models import Model


def step_seconds(gpu: GPU, m: Model, prefills: list[int], decodes: list[int]) -> float:
    """`prefills`: prompt tokens per request run this step. `decodes`: cached tokens per decoding request."""
    attn = 4 * m.layers * m.q_heads * m.head_dim  # attention FLOPs per (token, cached token) pair
    tokens = sum(prefills) + len(decodes)  # each decoding request adds one token
    flops = 2 * m.params * tokens
    flops += attn * sum(p * (p + 1) // 2 for p in prefills)  # prompt token i attends to i tokens
    flops += attn * sum(decodes)
    read = m.params * 2 + sum(decodes) * kv_bytes_per_token(m)  # weights once, then every cache
    return max(flops / gpu.peak_flops, read / gpu.bandwidth)

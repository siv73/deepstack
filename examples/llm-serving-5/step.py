"""Time for one engine step that mixes prefill chunks and decodes.

Part 3's step model, extended to chunks: a chunk of `c` prompt tokens that starts after `o`
tokens already in the cache attends to those `o` tokens too, and reads their keys and values.
Best case: 100% of peak, BF16 weights, KV writes and activations left out.
"""

from gpus import GPU
from kv_cache import kv_bytes_per_token
from models import Model


def step_seconds(gpu: GPU, m: Model, chunks: list[tuple[int, int]], decodes: list[int]) -> float:
    """`chunks`: (tokens already cached, tokens in this chunk) per prefilling request.
    `decodes`: cached tokens per decoding request (each adds one new token)."""
    attn = 4 * m.layers * m.q_heads * m.head_dim  # attention FLOPs per (token, cached token) pair
    tokens = sum(c for _, c in chunks) + len(decodes)
    flops = 2 * m.params * tokens
    flops += attn * sum(c * o + c * (c + 1) // 2 for o, c in chunks)  # token i of the chunk sees o + i
    flops += attn * sum(decodes)
    cached = sum(o for o, _ in chunks) + sum(decodes)  # keys and values read from the cache
    read = m.params * 2 + cached * kv_bytes_per_token(m)  # weights once, then every cache
    return max(flops / gpu.peak_flops, read / gpu.bandwidth)

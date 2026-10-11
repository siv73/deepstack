"""What one replica can sustain under TTFT and ITL targets, colocated or split into prefill/decode pools.

Built on the series' step model (Part 5's step.py, with Part 6's bytes per weight and FP8 peaks).
A tensor-parallel group of `tp` GPUs runs like one GPU with `tp` times the FLOP/s and bandwidth,
plus two all-reduces per layer per step (attention output and MLP output), added, not overlapped.
Best case: 100% of peak; queueing is left to the planner's headroom.
"""

import math

from fabric import LINKS, nvlink_each_way
from gpus import GPUS
from kv_cache import kv_bytes_per_token
from models import Model
from precision import BYTES, SCHEMES, dense_ops
from tp import fit

BUDGETS = (256, 512, 1024, 2048, 4096, 8192)  # max_num_batched_tokens values the planner tries


def allreduce_seconds(gpu_id: str, m: Model, tp: int, tokens: int, fixed_us: float = 0.0) -> float:
    if tp == 1:
        return 0.0
    size = tokens * m.q_heads * m.head_dim * 2  # one BF16 hidden vector per token
    ring = 2 * (tp - 1) / tp * size / nvlink_each_way(gpu_id)  # nccl-tests: t = S/B x 2(n-1)/n
    return 2 * m.layers * (fixed_us * 1e-6 + ring)


def group_step(gpu_id, m, dtype, tp, chunks, n_dec, dec_ctx, fixed_us=0.0) -> float:
    """One step on a TP group: `chunks` = (tokens already cached, tokens now) per prefilling
    request; `n_dec` decoding requests with `dec_ctx` cached tokens each."""
    g = GPUS[gpu_id]
    lin_peak, _ = dense_ops(gpu_id, g.peak_flops, SCHEMES[dtype].math)
    attn = 4 * m.layers * m.q_heads * m.head_dim  # FLOPs per (token, cached token) pair
    tokens = sum(c for _, c in chunks) + n_dec
    pairs = sum(c * o + c * (c + 1) // 2 for o, c in chunks) + n_dec * dec_ctx
    compute = 2 * m.params * tokens / (tp * lin_peak) + attn * pairs / (tp * g.peak_flops)
    cached = sum(o for o, _ in chunks) + n_dec * dec_ctx
    read = m.params * BYTES[dtype] + cached * kv_bytes_per_token(m, int(BYTES[dtype]))
    return max(compute, read / (tp * g.bandwidth)) + allreduce_seconds(gpu_id, m, tp, tokens, fixed_us)


def prompt_chunks(prompt: int, room: int) -> list[tuple[int, int]]:
    """Prefill work that fills `room` tokens of one step, as chunked prefill does: whole prompts
    plus a slice of the next one, or one slice of a long prompt centred on its middle."""
    if prompt <= room:
        whole, rest = divmod(room, prompt)
        return [(0, prompt)] * whole + ([(0, rest)] if rest else [])
    return [(prompt // 2 - room // 2, room)]


def colocated(gpu_id, m, dtype, tp, prompt, output, ttft_slo, itl_slo, fixed_us=0.0):
    """Best steady state of one replica that mixes prefill chunks into its decode steps."""
    cap, ctx, best = fit(gpu_id, m, dtype, tp, prompt + output), prompt + output // 2, None
    for budget in BUDGETS:
        for n in range(1, min(cap, budget - 1) + 1):
            room = budget - n
            f = n * prompt / ((output - 1) * room)  # share of steps that must carry prefill
            if f > 1:
                break  # prefill cannot keep up with this many decodes
            s_dec = group_step(gpu_id, m, dtype, tp, [], n, ctx, fixed_us)
            s_mix = group_step(gpu_id, m, dtype, tp, prompt_chunks(prompt, room), n, ctx, fixed_us)
            s_avg = f * s_mix + (1 - f) * s_dec
            itl_p99 = s_mix if f > 0.01 else s_dec  # more than 1% of gaps are mixed steps
            ttft = s_avg / 2 + math.ceil(prompt / room) * s_mix
            rate = n / ((output - 1) * s_avg)  # Little's law: n = rate x (output - 1) x step
            if itl_p99 <= itl_slo and ttft <= ttft_slo and (best is None or rate > best["rate"]):
                best = {"rate": rate, "running": n, "budget": budget, "itl": itl_p99, "ttft": ttft}
    return best


def decode_pool(gpu_id, m, dtype, tp, prompt, output, itl_slo, fixed_us=0.0):
    """A decode-only replica: the largest batch whose step stays under the ITL target."""
    cap, ctx, best = fit(gpu_id, m, dtype, tp, prompt + output), prompt + output // 2, None
    for n in range(1, cap + 1):
        s = group_step(gpu_id, m, dtype, tp, [], n, ctx, fixed_us)
        if s > itl_slo:
            break
        best = {"rate": n / ((output - 1) * s), "running": n, "itl": s}
    return best


def prefill_pool(gpu_id, m, dtype, tp, prompt, link="nvlink", budget=8192, fixed_us=0.0):
    """A prefill-only replica: prompts per second, and its part of TTFT including the KV transfer."""
    s = group_step(gpu_id, m, dtype, tp, prompt_chunks(prompt, budget), 0, 0, fixed_us)
    kv = prompt * kv_bytes_per_token(m, int(BYTES[dtype]))  # every GPU sends its 1/tp share at once
    return {
        "rate": budget / (prompt * s),  # full steps of `budget` prompt tokens
        "step": s,
        "latency": math.ceil(prompt / budget) * s,
        "transfer": kv / (tp * LINKS[link](gpu_id)),
        "kv_bytes": kv,
    }

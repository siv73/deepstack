"""Back-of-envelope continuous batching: the same arithmetic as the page's trade-off calculator.

Steady state, every request with the same prompt and output length. A step decodes n requests;
each arriving request adds its prefill to one step. Little's law ties n to the arrival rate:
n = rate x (output - 1) x step time. Usage: uv run steady_state.py 10 1000 250 1024
"""

import math
import sys

from gpus import GPU, GPUS
from kv_cache import kv_bytes_per_token
from models import MODELS, Model


def costs(gpu: GPU, m: Model, n: float, ctx: float, prompt: int) -> tuple[float, float]:
    """Seconds for a decode-only step of n requests, and for the same step plus one prefill."""
    attn = 4 * m.layers * m.q_heads * m.head_dim
    compute = n * (2 * m.params + attn * ctx) / gpu.peak_flops
    memory = (2 * m.params + n * ctx * kv_bytes_per_token(m)) / gpu.bandwidth
    prefill = (2 * m.params * prompt + attn * prompt * (prompt + 1) / 2) / gpu.peak_flops
    return max(compute, memory), max(compute + prefill, memory)


def estimate(gpu, m, rate, prompt, output, max_seqs, util=0.92, reserve_gb=3.0) -> dict:
    ctx = prompt + output / 2  # average cached tokens per running request
    budget = gpu.memory_gb * 1e9 * util - 2 * m.params - reserve_gb * 1e9
    cap = min(max_seqs, math.floor(budget / ((prompt + output) * kv_bytes_per_token(m))))
    if cap < 1:
        return {"fits": False}

    def gap(t: float) -> float:  # > 0 while t is too short to be the average step time
        d, d1 = costs(gpu, m, rate * (output - 1) * t, ctx, prompt)
        return d + rate * t * (d1 - d) - t

    t_cap = cap / (rate * (output - 1))  # the step time at which n reaches the cap
    if gap(t_cap) <= 0:
        lo, hi = 0.0, t_cap
        for _ in range(100):
            lo, hi = (lo, (lo + hi) / 2) if gap((lo + hi) / 2) <= 0 else ((lo + hi) / 2, hi)
        n, t, served = rate * (output - 1) * hi, hi, rate
    else:  # demand needs more running requests than allowed: a queue builds without limit
        d, d1 = costs(gpu, m, cap, ctx, prompt)
        n, t = cap, d + cap / (output - 1) * (d1 - d)
        served = cap / ((output - 1) * t)
    d, d1 = costs(gpu, m, n, ctx, prompt)
    return {
        "fits": True,
        "overloaded": served < rate,
        "running": n,
        "max_running": cap,
        "tpot_s": t,
        "ttft_s": t / 2 + d1 if served == rate else math.inf,  # wait for the current step, then own prefill
        "requests_per_s": served,
        "output_tokens_per_s": served * output,
        "kv_used_bytes": n * ctx * kv_bytes_per_token(m),
        "kv_budget_bytes": budget,
    }


if __name__ == "__main__":
    rate, prompt, output, seqs = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    for k, v in estimate(GPUS["h100-sxm"], MODELS["llama-3.1-8b"], rate, prompt, output, seqs).items():
        print(f"{k:>20}: {v:.4g}" if isinstance(v, float) else f"{k:>20}: {v}")

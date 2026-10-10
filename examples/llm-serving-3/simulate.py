"""Run one request trace under static and continuous batching and compare.

Usage: uv run simulate.py [arrivals_per_s] [requests] [max_batch]
"""

import math
import sys

from continuous import run_continuous
from gpus import GPUS
from kv_cache import kv_bytes_per_token
from models import MODELS
from static import run_static
from workload import make_trace

H100, LLAMA_8B = GPUS["h100-sxm"], MODELS["llama-3.1-8b"]
KV_TOKENS = (80e9 * 0.92 - 16e9 - 3e9) / kv_bytes_per_token(LLAMA_8B)  # Part 2's H100 budget: 416,565


def p99(xs: list[float]) -> float:
    return sorted(xs)[math.ceil(0.99 * len(xs)) - 1]  # nearest rank


def summarize(reqs, run: dict) -> dict:
    span = max(r.done for r in reqs) - min(r.arrival for r in reqs)
    ttft = [r.first - r.arrival for r in reqs]
    tpot = [(r.last - r.first) / (r.output - 1) for r in reqs if r.output > 1]  # vLLM's formula
    return {
        "output_tokens_per_s": sum(r.output for r in reqs) / span,
        "ttft_mean_s": sum(ttft) / len(ttft),
        "ttft_p99_s": p99(ttft),
        "tpot_mean_s": sum(tpot) / len(tpot),
        "e2e_mean_s": sum(r.done - r.arrival for r in reqs) / len(reqs),
        "worst_gap_s": max(r.max_gap for r in reqs),
        "gpu_idle_fraction": 1 - run["busy"] / span,
        "padding_fraction": run["padding_fraction"],
        "preemptions": run["preemptions"],
    }


def compare(rate: float, n: int, max_batch: int, kv_tokens: float = KV_TOKENS, **kw) -> dict:
    """Same trace, same GPU, same batch limit; only the scheduling policy differs."""
    a, b = make_trace(rate, n, **kw), make_trace(rate, n, **kw)
    return {
        "static": summarize(a, run_static(a, H100, LLAMA_8B, max_batch)),
        "continuous": summarize(b, run_continuous(b, H100, LLAMA_8B, max_batch, 8192, kv_tokens)),
    }


if __name__ == "__main__":
    rate, n, batch = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    for name, s in compare(rate, n, batch).items():
        print(f"{name:>10}: " + ", ".join(f"{k}={v:.4g}" for k, v in s.items()))

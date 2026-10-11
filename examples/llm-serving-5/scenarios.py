"""The page's experiments, each a small function the tests call. Usage: uv run scenarios.py

H100 SXM, Llama 3.1 8B in BF16, and Part 2's KV budget of about 416,565 tokens throughout.
"""

import random

from gpus import GPUS
from kv_cache import kv_bytes_per_token
from models import MODELS
from scheduler import Req, run
from slo import p99, summarize, ttft
from workload import make_trace

H100, LLAMA_8B = GPUS["h100-sxm"], MODELS["llama-3.1-8b"]
KV_TOKENS = (80e9 * 0.92 - 16e9 - 3e9) / kv_bytes_per_token(LLAMA_8B)


def stall(budget=8192, chunked=True, long_prefill=0, with_chat=False) -> dict:
    """20 streams decoding at 1,000 cached tokens; a 50,000-token prompt arrives at t = 0.
    with_chat: a 500-token chat prompt arrives 10 ms later, behind it in the queue."""
    streams = [Req(0.0, 1000, 600, cached=1000, made=1, scheduled=0.0) for _ in range(20)]
    long, chat = Req(0.0, 50_000, 2), Req(0.01, 500, 20)
    res = run([long, chat] if with_chat else [long], H100, LLAMA_8B, budget, chunked=chunked,
              long_prefill=long_prefill, running=streams)  # fmt: skip
    return {
        "steps": res["steps"],
        "long_ttft_s": ttft(long),
        "chat_ttft_s": ttft(chat) if with_chat else None,
        "worst_itl_s": max(g for s in streams for g in s.gaps),
    }


def chat_trace(rate: float, n: int, seed: int = 7) -> list[Req]:
    """Part 3's chat traffic: Poisson arrivals, prompts of 100 to 2,000, answers of 20 to 500."""
    return [Req(r.arrival, r.prompt, r.output) for r in make_trace(rate, n, seed)]


def load(rate: float, n: int = 3000, max_queued=None, ttft_slo=1.0, tpot_slo=0.05) -> dict:
    reqs = chat_trace(rate, n)
    res = run(reqs, H100, LLAMA_8B, kv_tokens=KV_TOKENS, max_queued=max_queued)
    peaks = {"waiting_peak": max(s["waiting"] for s in res["steps"]),
             "kv_usage_peak": max(s["kv_used"] for s in res["steps"]) / KV_TOKENS}  # fmt: skip
    return summarize(reqs, ttft_slo, tpot_slo) | peaks | {"preemptions": res["preemptions"]}


def tenants(rate_b=0.5, prompt_b=32_000, **kw) -> dict:
    """Tenant a: chat at 8 requests/s. Tenant b: `prompt_b`-token prompts, priority 1."""
    a = chat_trace(8, 800, seed=11)
    rng, t, b, end = random.Random(12), 0.0, [], max(r.arrival for r in a)
    while (t := t + rng.expovariate(rate_b)) <= end:
        b.append(Req(t, prompt_b, 50, priority=1, tenant="b"))
    run(a + b, H100, LLAMA_8B, kv_tokens=KV_TOKENS, **kw)
    s = summarize(a, 1.0, 0.05)
    return {"a_ttft_p99_s": s["ttft_p99_s"], "a_itl_p99_s": s["itl_p99_s"],
            "a_slo_attainment": s["slo_attainment"], "b_ttft_p99_s": p99([ttft(r) for r in b]),
            "b_requests": len(b)}  # fmt: skip


if __name__ == "__main__":
    for b, c in [(65536, False), (8192, True), (2048, True)]:
        s = stall(b, c)
        print(f"budget {b:>6} chunked={c}: long TTFT {s['long_ttft_s']:.3f} s, ", end="")
        print(f"worst ITL {s['worst_itl_s']:.3f} s")
    for rate, cap in [(4, None), (40, None), (40, 300)]:
        s = load(rate, max_queued=cap)
        print(f"{rate} req/s, queue cap {cap}: {s['requests_per_s']:.1f} req/s, ", end="")
        print(f"goodput {s['goodput_per_s']:.1f}")

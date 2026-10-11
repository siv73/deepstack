"""SLO checks and goodput, computed the way vLLM's benchmark does it.

vllm bench serve --goodput counts a request as good when every SLO it was given holds
(TTFT, TPOT, end-to-end), and reports good requests per second of benchmark time.
TPOT per request is (end-to-end latency - TTFT) / (output tokens - 1), 0 for one-token answers.
"""

import math


def p99(xs: list[float]) -> float:
    return sorted(xs)[math.ceil(0.99 * len(xs)) - 1] if xs else 0.0  # nearest rank


def ttft(r) -> float:
    return r.first - r.arrival


def tpot(r) -> float:
    return (r.last - r.first) / (r.output - 1) if r.output > 1 else 0.0


def is_good(r, ttft_slo: float, tpot_slo: float) -> bool:
    return not r.rejected and ttft(r) <= ttft_slo and tpot(r) <= tpot_slo


def summarize(reqs, ttft_slo: float = 2.0, tpot_slo: float = 0.05) -> dict:
    served = [r for r in reqs if not r.rejected]
    span = max(r.done for r in served) - min(r.arrival for r in reqs)  # benchmark duration
    good = sum(is_good(r, ttft_slo, tpot_slo) for r in reqs)
    gaps = [g for r in served for g in r.gaps]
    return {
        "requests_per_s": len(served) / span,  # raw throughput
        "output_tokens_per_s": sum(r.output for r in served) / span,
        "goodput_per_s": good / span,  # requests that met every SLO, per second
        "slo_attainment": good / len(reqs),
        "ttft_p99_s": p99([ttft(r) for r in served]),
        "tpot_p99_s": p99([tpot(r) for r in served]),
        "itl_p99_s": p99(gaps),
        "itl_max_s": max(gaps, default=0.0),
        "queue_p99_s": p99([r.scheduled - r.arrival for r in served]),
        "rejected": len(reqs) - len(served),
        "preempted_requests": sum(r.preempted > 0 for r in served),
    }

"""Expected gain from speculative decoding: the paper's formula, then the same round on the roofline.

alpha: chance the target accepts a draft token (assumed the same at every position).
k: draft tokens per round. c: one draft step's time as a fraction of one target decode step.
"""

from models import Model
from quant import step_seconds


def tokens_per_round(k: int, alpha: float) -> float:
    """Leviathan et al., Eq. 1: accepted prefix plus the target's own token."""
    return k + 1 if alpha == 1 else (1 - alpha ** (k + 1)) / (1 - alpha)


def draft_acceptance_rate(k: int, alpha: float) -> float:
    """What vLLM reports: accepted draft tokens / proposed draft tokens."""
    return (tokens_per_round(k, alpha) - 1) / k


def paper_speedup(k: int, alpha: float, c: float) -> float:
    """Leviathan et al., Theorem 3.8: verifying k+1 tokens costs the same as decoding one."""
    return tokens_per_round(k, alpha) / (k * c + 1)


def served(gpu_id: str, m: Model, scheme: str, kv: str, batch: int, context: int,
           k: int, alpha: float, c: float) -> dict:  # fmt: skip
    """One round for a whole batch: k draft steps, then one target pass over k+1 positions each."""
    plain, _, _ = step_seconds(gpu_id, m, scheme, kv, batch, context)
    verify, bound, _ = step_seconds(gpu_id, m, scheme, kv, batch, context, tokens=k + 1)
    round_s = k * c * plain + verify
    e = tokens_per_round(k, alpha)
    return {
        "verify_over_plain": verify / plain,
        "verify_bound": bound,
        "tokens_per_s": batch * e / round_s,
        "speedup": (batch * e / round_s) / (batch / plain),
        "tpot_s": round_s / e,  # per token, averaged
        "gap_s": round_s,  # between streamed outputs: a whole round's tokens arrive together
    }

"""The chunk-budget calculator's arithmetic: what one token budget does to a fixed prompt mix.

`streams` requests decode steadily at about `ctx` cached tokens each. Long prompts of `prompt`
tokens arrive `per_min` times a minute and are chunked into whatever the budget leaves after the
decodes. Same step model as step.py. Usage: uv run chunk_budget.py 8192
"""

import sys

from gpus import GPUS
from models import MODELS
from step import step_seconds


def chunk_steps(gpu, m, budget: int, streams: int, ctx: int, prompt: int) -> list[float]:
    """Seconds for each step that carries a chunk of the long prompt (decodes go first)."""
    room, done, out = budget - streams, 0, []
    assert room > 0, "the decodes alone fill the budget"
    while done < prompt:
        c = min(prompt - done, room)
        out.append(step_seconds(gpu, m, [(done, c)], [ctx + len(out)] * streams))
        done += c
    return out


def estimate(gpu, m, budget=8192, streams=20, ctx=1000, prompt=50_000, per_min=2.0,
             output=300, ttft_slo=2.0, tpot_slo=0.05, itl_slo=0.1) -> dict:  # fmt: skip
    decode = step_seconds(gpu, m, [], [ctx] * streams)
    chunks = chunk_steps(gpu, m, budget, streams, ctx, prompt)
    busy = per_min * sum(chunks) / 60  # share of each minute spent on long-prompt steps
    if busy >= 1:
        return {"overloaded": True, "decode_s": decode, "worst_step_s": max(chunks)}
    plain = (1 - busy) * 60 / decode  # decode-only steps per minute
    total = plain + per_min * len(chunks)  # every step gives each stream one token
    rank, seen, p99 = 0.99 * total, 0.0, decode
    for gap, count in sorted([(decode, plain)] + [(s, per_min) for s in chunks]):
        seen += count
        if seen >= rank:
            p99 = gap
            break
    late = (per_min * sum(s > itl_slo for s in chunks) + plain * (decode > itl_slo)) / total
    itl_mean = 60 / total
    chat_rate = streams / (output * itl_mean)  # requests finishing per second (Little's law)
    long_rate = per_min / 60
    # vLLM-style goodput: a chat stream's TPOT is the mean gap, so rare stalls barely move it
    good = chat_rate * (itl_mean <= tpot_slo) + long_rate * (sum(chunks) <= ttft_slo)
    return {
        "overloaded": False,
        "decode_s": decode,
        "worst_step_s": max(chunks),
        "chunk_steps": len(chunks),
        "long_ttft_s": sum(chunks),  # arrives at an empty queue
        "itl_mean_s": itl_mean,
        "itl_p99_s": p99,
        "late_token_share": late,  # tokens that arrived more than itl_slo after the previous one
        "requests_per_s": chat_rate + long_rate,
        "goodput_per_s": good,
    }


if __name__ == "__main__":
    est = estimate(GPUS["h100-sxm"], MODELS["llama-3.1-8b"], budget=int(sys.argv[1]))
    for k, v in est.items():
        print(f"{k:>15}: {v:.4g}" if isinstance(v, float) else f"{k:>15}: {v}")

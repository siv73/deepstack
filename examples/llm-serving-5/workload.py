"""A reproducible request trace: Poisson arrivals, random prompt and output lengths."""

import random
from dataclasses import dataclass


@dataclass
class Request:
    arrival: float  # seconds
    prompt: int  # prompt tokens
    output: int  # tokens to generate (the first comes out of prefill)
    first: float = 0.0  # when the first output token was produced
    last: float = 0.0  # when the last output token was produced
    done: float = 0.0  # when the full response went back to the client
    max_gap: float = 0.0  # longest wait between two of its own tokens
    preempted: int = 0


def make_trace(rate: float, n: int, seed: int = 7, prompt=(100, 2000), output=(20, 500)) -> list[Request]:
    rng, t, out = random.Random(seed), 0.0, []
    for _ in range(n):
        t += rng.expovariate(rate)
        out.append(Request(t, rng.randint(*prompt), rng.randint(*output)))
    return out

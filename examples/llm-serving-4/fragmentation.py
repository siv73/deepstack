"""Memory wasted by contiguous max-length reservation versus paged blocks, and what it costs in batch size.

Lengths are each request's final length (prompt + output). A contiguous allocator reserves
max_len slots per request; a paged one holds ceil(length / block_size) blocks. External
fragmentation depends on the allocator and is not modelled, so the contiguous figures are a
best case for it. Usage: uv run fragmentation.py 2048 16 120,450,800,1500,300,2048,60,900
"""

import math
import sys


def blocks_for(tokens: int, block_size: int) -> int:
    return -(-tokens // block_size)


def report(
    lengths: list[int], max_len: int, block_size: int, kv_bytes_per_token: int, budget_bytes: float
) -> dict:
    if not lengths or min(lengths) < 1 or max(lengths) > max_len:
        raise ValueError("every length must be between 1 and max_len")
    n, used = len(lengths), sum(lengths)
    contiguous = n * max_len
    paged = sum(blocks_for(x, block_size) for x in lengths) * block_size
    budget_tokens = budget_bytes / kv_bytes_per_token
    return {
        "requests": n,
        "used_tokens": used,
        "contiguous_tokens": contiguous,
        "paged_tokens": paged,
        "contiguous_waste": 1 - used / contiguous,
        "paged_waste": 1 - used / paged,
        "contiguous_bytes": contiguous * kv_bytes_per_token,
        "paged_bytes": paged * kv_bytes_per_token,
        # requests that fit at once if new ones keep arriving with this same mix of lengths
        "contiguous_capacity": math.floor(budget_tokens / max_len),
        "paged_capacity": math.floor(budget_tokens * n / paged),
    }


if __name__ == "__main__":
    max_len, bs = int(sys.argv[1]), int(sys.argv[2])
    lengths = [int(x) for x in sys.argv[3].split(",")]
    r = report(lengths, max_len, bs, kv_bytes_per_token=131_072, budget_bytes=54.6e9)
    for kind in ("contiguous", "paged"):
        slots, waste, fits = r[f"{kind}_tokens"], r[f"{kind}_waste"], r[f"{kind}_capacity"]
        print(f"{kind:>10}: {slots:,} slots, {waste:.1%} wasted, fits {fits}")

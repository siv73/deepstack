"""Prefix caching: a full block is named by its parent's hash, its tokens and any extra key.

Modelled on vLLM v0.31.0's design doc (docs/design/prefix_caching.md); simplified.
"""

import hashlib

from pool import Block, BlockPool


def block_hash(parent: str | None, tokens: list[int], extra: str = "") -> str:
    return hashlib.sha256(repr((parent, tuple(tokens), extra)).encode()).hexdigest()


def find_hits(pool: BlockPool, prompt: list[int], block_size: int, salt: str = "") -> list[Block]:
    """Cached blocks that match the prompt's leading full blocks, stopping at the first miss."""
    hits, parent = [], None
    for i in range((len(prompt) - 1) // block_size):  # full blocks only; the last token is always computed
        h = block_hash(parent, prompt[i * block_size : (i + 1) * block_size], salt if i == 0 else "")
        if h not in pool.cached:
            break
        hits.append(pool.blocks[pool.cached[h]])
        parent = h
    return hits


def cache_if_full(pool: BlockPool, table: list[int], i: int, block_size: int, salt: str = "") -> None:
    """Name block i of a table once it is full, so later requests can find it."""
    b = pool.blocks[table[i]]
    if b.hash is not None or len(b.tokens) < block_size:
        return
    parent = pool.blocks[table[i - 1]].hash if i else None
    b.hash = block_hash(parent, b.tokens, salt if i == 0 else "")
    pool.cached.setdefault(b.hash, b.id)  # an identical block may be cached already; keep the first

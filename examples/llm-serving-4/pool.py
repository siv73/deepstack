"""The block pool: every KV block made up front, a free queue, and reference counts.

Modelled on vLLM v0.31.0's BlockPool (vllm/v1/core/block_pool.py); simplified.
"""

from collections import OrderedDict
from dataclasses import dataclass, field


class OutOfBlocks(Exception):
    """No free block left: the caller must wait, or preempt someone."""


@dataclass
class Block:
    id: int
    ref_cnt: int = 0  # how many block tables point here
    tokens: list[int] = field(default_factory=list)
    hash: str | None = None  # set once the block is full and cached


class BlockPool:
    def __init__(self, num_blocks: int):
        self.blocks = [Block(i) for i in range(num_blocks)]
        self.free_q = OrderedDict.fromkeys(range(num_blocks))  # free blocks; the head goes out first
        self.cached: dict[str, int] = {}  # block hash -> block id

    def num_free(self) -> int:
        return len(self.free_q)

    def take(self) -> Block:
        if not self.free_q:
            raise OutOfBlocks
        b = self.blocks[self.free_q.popitem(last=False)[0]]
        if b.hash is not None:  # reusing a cached block evicts it from the cache
            if self.cached.get(b.hash) == b.id:
                del self.cached[b.hash]
            b.hash = None
        b.ref_cnt, b.tokens = 1, []
        return b

    def touch(self, b: Block) -> None:
        if b.ref_cnt == 0:
            del self.free_q[b.id]  # free but still cached: take it off the queue
        b.ref_cnt += 1

    def release(self, b: Block) -> None:
        b.ref_cnt -= 1
        if b.ref_cnt == 0:
            self.free_q[b.id] = None  # cached block: back of the queue, so LRU goes first
            if b.hash is None:
                self.free_q.move_to_end(b.id, last=False)  # nothing to reuse: hand it out first

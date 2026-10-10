"""A toy paged KV cache: block tables, copy-on-write forks and prefix reuse over pool.py.

Bookkeeping only: it tracks which block holds which tokens, never the keys and values.
"""

from dataclasses import dataclass, field

from hashing import cache_if_full, find_hits
from pool import BlockPool, OutOfBlocks


@dataclass
class Seq:
    table: list[int] = field(default_factory=list)  # logical block i -> physical block id
    tokens: list[int] = field(default_factory=list)
    salt: str = ""


class BlockAllocator:
    def __init__(self, num_blocks: int, block_size: int, caching: bool = True):
        self.pool, self.block_size, self.caching = BlockPool(num_blocks), block_size, caching
        self.seqs: dict[str, Seq] = {}
        self.copies: list[tuple[int, int]] = []  # (from, to) block copies made by copy-on-write

    def allocate(self, rid: str, prompt: list[int], salt: str = "") -> int:
        """Blocks for a new prompt and nothing more. Returns the prompt tokens that hit the cache."""
        hits = find_hits(self.pool, prompt, self.block_size, salt) if self.caching else []
        need = -(-len(prompt) // self.block_size) - len(hits)
        if need > self.pool.num_free() - sum(b.ref_cnt == 0 for b in hits):
            raise OutOfBlocks  # checked first, so a refused request changes nothing
        for b in hits:
            self.pool.touch(b)
        seq = self.seqs[rid] = Seq([b.id for b in hits], prompt[: len(hits) * self.block_size], salt)
        for t in prompt[len(seq.tokens) :]:
            self._write(seq, t)
        return len(hits) * self.block_size

    def append(self, rid: str, token: int) -> None:
        self._write(self.seqs[rid], token)  # one decode step

    def _write(self, seq: Seq, token: int) -> None:
        if len(seq.tokens) % self.block_size == 0:  # last block full, or none yet
            seq.table.append(self.pool.take().id)
        last = self.pool.blocks[seq.table[-1]]
        if last.ref_cnt > 1:  # shared and not full: copy on write
            new = self.pool.take()
            new.tokens = list(last.tokens)
            self.copies.append((last.id, new.id))
            self.pool.release(last)
            seq.table[-1], last = new.id, new
        last.tokens.append(token)
        seq.tokens.append(token)
        if self.caching:
            cache_if_full(self.pool, seq.table, len(seq.table) - 1, self.block_size, seq.salt)

    def fork(self, parent: str, child: str) -> None:
        """A second sample of the same prompt: share every block, copy nothing yet."""
        p = self.seqs[parent]
        for bid in p.table:
            self.pool.blocks[bid].ref_cnt += 1
        self.seqs[child] = Seq(list(p.table), list(p.tokens), p.salt)

    def free(self, rid: str) -> None:
        for bid in reversed(self.seqs.pop(rid).table):  # last block first, so it is evicted first
            self.pool.release(self.pool.blocks[bid])

    def table(self, rid: str) -> list[int]:
        return list(self.seqs[rid].table)

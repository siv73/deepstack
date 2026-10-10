"""The step-through diagram's data: three requests sharing a 12-block pool, block size 4.

Each step is a snapshot of the pool and every block table, produced by running allocator.py.
The page's .ts-blocks JSON is this output; a test checks they match.
Usage: uv run block_trace.py
"""

import json

from allocator import BlockAllocator

CAPTIONS = [
    (
        "A arrives with a 6-token prompt. It gets two blocks: 4 tokens in block 0, 2 in block 1. Nothing "
        "is reserved for its answer."
    ),
    (
        "B arrives with 3 tokens and gets one block. C arrives with 9 tokens and gets three. 6 of 12 "
        "blocks are in use."
    ),
    ("One decode step: each request writes one token into the free slot of its last block. No new blocks."),
    (
        "Next step: A fills block 1 exactly. B's block was full, so B takes block 6. Its table now points"
        " at blocks 2 and 6, which are not next to each other."
    ),
    ("Next step: A needs a new block and takes block 7. C fills its last block."),
    (
        "C finishes. Its three blocks go straight back to the free list and can be handed to anyone. No "
        "gaps are left behind."
    ),
    (
        "B asks for two samples. The second sample, B2, gets a copy of B's block table: blocks 2 and 6 "
        "now have two owners each. No data is copied."
    ),
    (
        "B writes a token. Its last block is shared, so it gets a private copy first (block 6 is copied "
        "into block 3), then writes there."
    ),
    ("B2 writes a token. Block 6 now has one owner, so B2 writes in place. Only one block was ever copied."),
]


def snapshot(a: BlockAllocator) -> dict:
    owners = {i: [] for i in range(len(a.pool.blocks))}
    for rid, seq in a.seqs.items():
        for bid in seq.table:
            owners[bid].append(rid)
    return {
        "pool": [[len(b.tokens) if b.ref_cnt else 0, b.ref_cnt, owners[b.id]] for b in a.pool.blocks],
        "tables": [[rid, list(seq.table), len(seq.tokens)] for rid, seq in a.seqs.items()],
    }


def run() -> dict:
    a = BlockAllocator(num_blocks=12, block_size=4, caching=False)
    steps = []
    tok = iter(range(10_000))

    def grow(*rids):
        for r in rids:
            a.append(r, next(tok))

    def snap(copy=None):
        s = snapshot(a)
        s["copy"] = copy
        steps.append(s)

    a.allocate("A", [next(tok) for _ in range(6)])
    snap()
    a.allocate("B", [next(tok) for _ in range(3)])
    a.allocate("C", [next(tok) for _ in range(9)])
    snap()
    grow("A", "B", "C")
    snap()
    grow("A", "B", "C")
    snap()
    grow("A", "B", "C")
    snap()
    a.free("C")
    snap()
    a.fork("B", "B2")
    snap()
    grow("B")
    snap(list(a.copies[-1]))
    grow("B2")
    snap()
    return {"blocks": 12, "block_size": 4, "steps": steps, "captions": CAPTIONS}


if __name__ == "__main__":
    print(json.dumps(run(), separators=(",", ":")))

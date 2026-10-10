"""Every behaviour and number the page claims for the toy allocator, the calculator and the diagram."""

import json
import re
import subprocess
import sys
from pathlib import Path

import block_trace as tr
import pytest
from allocator import BlockAllocator
from fragmentation import blocks_for, report
from gpus import GPUS
from models import MODELS
from pool import OutOfBlocks
from pool_size import bytes_per_block, num_blocks

HERE = Path(__file__).parent
BODY = HERE.parent.parent / "content" / "llm-serving-4" / "body.html"
LLAMA_8B, H100 = MODELS["llama-3.1-8b"], GPUS["h100-sxm"]
KV_PER_TOKEN = 131_072  # Part 2: 2 x 32 layers x 8 KV heads x 128 x 2 bytes


@pytest.mark.parametrize("name", ["gpus.py", "models.py"])
def test_shapes_are_part3s_unchanged(name):
    assert (HERE / name).read_text() == (HERE.parent / "llm-serving-3" / name).read_text()


def toks(n, start=0):
    return list(range(start, start + n))


# ---------- block tables: allocate, append, free ----------
def test_prompt_gets_only_the_blocks_it_fills():
    a = BlockAllocator(12, 4, caching=False)
    a.allocate("A", toks(6))
    assert a.table("A") == [0, 1] and a.pool.num_free() == 10  # nothing reserved for the answer


def test_append_takes_a_new_block_only_at_a_block_boundary():
    a = BlockAllocator(12, 4, caching=False)
    a.allocate("A", toks(6))
    a.append("A", 100)
    a.append("A", 101)
    assert a.table("A") == [0, 1]  # 8 tokens: the second block is now full
    a.append("A", 102)
    assert a.table("A") == [0, 1, 2]


def test_block_table_is_not_contiguous_when_requests_interleave():
    data = tr.run()
    assert data["steps"][3]["tables"][1] == ["B", [2, 6], 5]


def test_waste_is_at_most_one_partly_filled_block_per_request():
    a = BlockAllocator(64, 16, caching=False)
    for i, n in enumerate([1, 15, 16, 17, 300]):
        a.allocate(str(i), toks(n))
        assert len(a.table(str(i))) * 16 - n < 16


def test_free_returns_every_block_and_they_are_reused():
    a = BlockAllocator(4, 4, caching=False)
    a.allocate("A", toks(16))
    with pytest.raises(OutOfBlocks):
        a.allocate("B", toks(1))
    a.free("A")
    assert a.pool.num_free() == 4
    a.allocate("B", toks(16))  # any free block will do: no contiguous run needed
    assert sorted(a.table("B")) == [0, 1, 2, 3]


def test_out_of_blocks_changes_nothing():
    a = BlockAllocator(3, 4, caching=False)
    a.allocate("A", toks(8))
    with pytest.raises(OutOfBlocks):
        a.allocate("B", toks(5))  # needs 2 blocks, 1 is free
    assert a.pool.num_free() == 1 and "B" not in a.seqs


# ---------- copy-on-write fork ----------
def test_fork_shares_blocks_and_copies_nothing():
    a = BlockAllocator(12, 4, caching=False)
    a.allocate("B", toks(6))
    a.fork("B", "B2")
    assert a.table("B2") == a.table("B") == [0, 1]
    assert [a.pool.blocks[i].ref_cnt for i in (0, 1)] == [2, 2] and a.copies == []


def test_first_write_to_a_shared_block_copies_it_once():
    a = BlockAllocator(12, 4, caching=False)
    a.allocate("B", toks(6))
    a.fork("B", "B2")
    a.append("B", 7)
    assert a.copies == [(1, 2)] and a.table("B") == [0, 2]
    assert a.pool.blocks[2].tokens == [4, 5, 7]  # copied, then written
    a.append("B2", 9)
    assert a.copies == [(1, 2)] and a.table("B2") == [0, 1]  # sole owner now: writes in place
    assert a.pool.blocks[1].tokens == [4, 5, 9]
    assert a.pool.blocks[0].ref_cnt == 2  # the full prompt block stays shared


def test_fork_on_a_block_boundary_needs_no_copy():
    a = BlockAllocator(12, 4, caching=False)
    a.allocate("B", toks(8))
    a.fork("B", "B2")
    a.append("B", 1)
    a.append("B2", 2)
    assert a.copies == [] and a.table("B") == [0, 1, 2] and a.table("B2") == [0, 1, 3]


def test_shared_block_is_freed_only_when_its_last_owner_finishes():
    a = BlockAllocator(12, 4, caching=False)
    a.allocate("B", toks(8))
    a.fork("B", "B2")
    a.free("B")
    assert a.pool.num_free() == 10
    a.free("B2")
    assert a.pool.num_free() == 12


# ---------- prefix caching ----------
def test_only_full_blocks_of_a_shared_prefix_hit():
    a = BlockAllocator(10, 4)
    a.allocate("R0", toks(15))
    shared = toks(10) + [900, 901, 902, 903]  # first 10 tokens match R0
    assert a.allocate("R1", shared) == 8  # the third block matches 2 of 4 tokens: a miss
    assert a.table("R1")[:2] == a.table("R0")[:2]
    assert a.pool.blocks[0].ref_cnt == 2


def test_a_fully_cached_prompt_still_computes_its_last_token():
    a = BlockAllocator(10, 4)
    a.allocate("R0", toks(8))
    assert a.allocate("R1", toks(8)) == 4  # 7 tokens could hit; only 1 full block of them


def test_hash_covers_the_prefix_not_just_the_block():
    a = BlockAllocator(10, 4)
    a.allocate("R0", toks(8))
    assert a.allocate("R1", [99, 98, 97, 96] + toks(4, 4) + [0]) == 0  # same second block, different parent


def test_cache_salt_isolates_prefixes():
    a = BlockAllocator(10, 4)
    a.allocate("R0", toks(9), salt="team-a")
    assert a.allocate("R1", toks(9), salt="team-b") == 0
    assert a.allocate("R2", toks(9), salt="team-a") == 8


def test_freed_cached_blocks_stay_reusable_until_evicted():
    a = BlockAllocator(4, 4)
    a.allocate("R0", toks(9))  # blocks 0,1 cached, block 2 partial
    a.free("R0")
    assert a.pool.num_free() == 4  # counted as free...
    assert a.allocate("R1", toks(9)) == 8  # ...but still hit


def test_lru_eviction_drops_the_cached_block():
    a = BlockAllocator(3, 4)
    a.allocate("R0", toks(5))  # block 0 cached, block 1 partial
    a.free("R0")
    a.allocate("X", toks(12, 50))  # needs all 3 blocks: the cached one is evicted
    a.free("X")
    assert a.allocate("R1", toks(5)) == 0


def test_free_queue_order_follows_v031_source_not_the_design_doc_example():
    # The design doc's example (block size 4, 10 blocks), replayed on the toy.
    a = BlockAllocator(10, 4)
    r0 = toks(15)
    a.allocate("R0", r0)  # blocks 0-3; 0, 1, 2 full and cached
    a.append("R0", 15)  # block 3 full and cached
    a.append("R0", 16)  # block 4
    assert a.table("R0") == [0, 1, 2, 3, 4]
    assert a.allocate("R1", toks(10) + [700, 701, 702, 703]) == 8
    assert a.table("R1") == [0, 1, 5, 6]
    a.free("R0")
    a.free("R1")
    # Unhashed blocks (6, 4) go to the head; cached ones go to the tail, last block first.
    assert list(a.pool.free_q) == [6, 4, 7, 8, 9, 3, 2, 5, 1, 0]
    assert a.allocate("R2", toks(12) + [800 + i for i in range(17)]) == 12
    assert a.table("R2") == [0, 1, 2, 6, 4, 7, 8, 9]  # the doc's example shows 7, 8, 9, 4, 3


# ---------- fragmentation report and pool size ----------
SAMPLE = [120, 450, 800, 1500, 300, 2048, 60, 900]
BUDGET = 54.6e9


def test_pool_budget_matches_part3():
    assert H100.memory_gb * 1e9 * 0.92 - LLAMA_8B.params * 2 - 3e9 == pytest.approx(BUDGET)


def test_one_request_reserved_at_max_length():
    assert 2048 * KV_PER_TOKEN == 268_435_456  # 256 MiB
    assert 300 * KV_PER_TOKEN == 39_321_600
    assert pytest.approx(0.854, abs=5e-4) == 1 - 300 / 2048
    assert blocks_for(300, 16) == 19 and 19 * 16 - 300 == 4


def test_sample_mix_contiguous_vs_paged():
    r = report(SAMPLE, 2048, 16, KV_PER_TOKEN, BUDGET)
    assert r["used_tokens"] == 6178 and r["contiguous_tokens"] == 16384 and r["paged_tokens"] == 6224
    assert r["contiguous_waste"] == pytest.approx(0.623, abs=5e-4)
    assert r["paged_waste"] == pytest.approx(0.0074, abs=5e-5)
    assert (r["contiguous_capacity"], r["paged_capacity"]) == (203, 535)


def test_report_rejects_lengths_over_the_limit():
    with pytest.raises(ValueError):
        report([2049], 2048, 16, KV_PER_TOKEN, BUDGET)


def test_block_pool_size_for_llama_8b_on_h100():
    assert bytes_per_block(LLAMA_8B, 16) == 2_097_152 == 16 * KV_PER_TOKEN  # 2 MiB
    assert num_blocks(H100, LLAMA_8B) == 26_035
    assert num_blocks(H100, LLAMA_8B) * 16 == 416_560


def test_cli_runs():
    out = subprocess.run(
        [sys.executable, "fragmentation.py", "2048", "16", ",".join(map(str, SAMPLE))],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "62.3% wasted, fits 203" in out and "0.7% wasted, fits 535" in out


# ---------- the page's diagram and calculator ----------
def test_page_diagram_matches_the_code():
    spec = re.search(
        r'class="ts-blocks".*?<script type="application/json">(.*?)</script>', BODY.read_text(), re.S
    )
    assert spec, "no .ts-blocks figure on the page"
    assert json.loads(spec.group(1)) == tr.run()


def test_page_calculator_defaults_match_the_worked_example():
    spec = re.search(
        r'class="ts-fragcalc".*?<script type="application/json">(.*?)</script>', BODY.read_text(), re.S
    )
    assert spec, "no .ts-fragcalc on the page"
    d = json.loads(spec.group(1))["defaults"]
    assert [int(x) for x in d["lengths"].split(",")] == SAMPLE
    assert (d["max_len"], d["block_size"], d["kv_bytes"], d["budget_gb"]) == (2048, 16, KV_PER_TOKEN, 54.6)


# ---------- numbers quoted in the problems and the interview drill ----------
def test_four_samples_store_the_prompt_once_or_four_times():
    assert 4 * 1000 * KV_PER_TOKEN == 524_288_000 and 1000 * KV_PER_TOKEN == 131_072_000


def test_shared_system_prompt_drill():
    assert divmod(2500, 16) == (156, 4)
    assert 400 * 2500 * KV_PER_TOKEN == 131_072_000_000 > BUDGET  # does not fit
    assert 156 * 16 * KV_PER_TOKEN == 327_155_712  # the 156 shared full blocks: about 327 MB


def test_preempted_request_readmission():
    blocks = 1200 // 16
    assert blocks == 75 and (blocks - 30) * 16 == 720 and 1200 - 720 == 480


def test_preempted_blocks_leave_the_free_queue_tail_first():
    a = BlockAllocator(10, 4)
    a.allocate("R", toks(16))  # 4 full, cached blocks
    a.free("R")  # freed last block first; cached blocks join the back of the queue
    a.allocate("X", toks(24, 100))  # takes the 6 never-used blocks
    a.allocate("Y", toks(8, 200))  # takes R's blocks 3 and 2, its tail
    assert sorted(a.table("Y")) == [2, 3]
    a.free("X")
    assert a.allocate("R2", toks(16)) == 8  # R's first two blocks still hit

# ruff: noqa: E501
"""plan_lint on plans shaped like PostgreSQL 18 EXPLAIN (ANALYZE) text output."""

from plan_lint import lint

CORRELATED = """\
Nested Loop  (cost=0.42..33426.20 rows=128 width=12) (actual time=0.021..85.331 rows=2500.00 loops=1)
  Buffers: shared hit=27991 read=5903
  ->  Seq Scan on payments p  (cost=0.00..31394.00 rows=255 width=8) (actual time=0.014..76.228 rows=5000.00 loops=1)
        Filter: ((city = 'c7'::text) AND (state = 's0'::text))
        Rows Removed by Filter: 995000
  ->  Index Scan using orders_pkey on orders o  (cost=0.42..7.97 rows=1 width=12) (actual time=0.002..0.002 rows=0.50 loops=5000)
        Index Cond: (id = p.id)
        Index Searches: 5000
"""

SPILLING = """\
Hash Join  (cost=16389.00..31748.51 rows=500000 width=8) (actual time=110.941..301.048 rows=500000.00 loops=1)
  Hash Cond: (o1.id = o2.id)
  ->  Seq Scan on orders o1  (cost=0.00..8185.00 rows=500000 width=8) (actual time=0.006..37.937 rows=500000.00 loops=1)
  ->  Hash  (cost=8185.00..8185.00 rows=500000 width=8) (actual time=110.466..110.467 rows=500000.00 loops=1)
        Buckets: 65536  Batches: 16  Memory Usage: 1732kB
        ->  Seq Scan on orders o2  (cost=0.00..8185.00 rows=500000 width=8) (actual time=0.004..43.540 rows=500000.00 loops=1)
Sort  (cost=1.00..2.00 rows=10 width=4) (actual time=1.0..2.0 rows=10.00 loops=1)
  Sort Method: external merge  Disk: 14720kB
"""


def test_underestimate_that_drove_5000_inner_loops_is_flagged():
    found = lint(CORRELATED)
    assert found == ["Nested Loop: estimated 128 rows, got 2500", "Seq Scan: estimated 255 rows, got 5000"]


def test_per_loop_figures_are_multiplied_by_loops():
    # 1 estimated x 5000 loops = 5000 vs 0.5 x 5000 = 2500: within 10x, not flagged
    assert not any(f.startswith("Index Scan") for f in lint(CORRELATED))


def test_spills_are_reported():
    found = lint(SPILLING)
    assert "Hash: hash used 16 batches (spilled to disk)" in found
    assert "Sort: sort spilled to disk" in found


def test_lossy_bitmap_is_reported():
    plan = (
        "Bitmap Heap Scan on orders  (cost=1.00..2.00 rows=45000 width=8) "
        "(actual time=1.7..26.2 rows=45000.00 loops=1)\n"
        "  Heap Blocks: exact=849 lossy=2065\n"
    )
    assert lint(plan) == ["Bitmap Heap Scan: bitmap went lossy, every row on those pages rechecked"]


def test_older_integer_row_counts_still_parse():
    plan = "Seq Scan on t  (cost=0.00..170.00 rows=1 width=8) (actual time=0.01..1.2 rows=100 loops=1)\n"
    assert lint(plan) == ["Seq Scan: estimated 1 rows, got 100"]

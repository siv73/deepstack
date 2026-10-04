"""Cost units: the documented sequential-scan arithmetic, and how random_page_cost moves the crossover."""

import pytest
from costs import crossover_fraction, seq_scan_cost, toy_index_scan_cost


def test_seq_scan_matches_the_docs_example():
    # tenk1: 345 pages, 10,000 rows (PostgreSQL 18 docs, "EXPLAIN Basics")
    assert seq_scan_cost(345, 10_000) == pytest.approx(445)
    assert seq_scan_cost(345, 10_000, quals=1) == pytest.approx(470)


def test_index_scan_is_cheap_for_few_rows_and_ruinous_for_many():
    seq = seq_scan_cost(16_394, 1_000_000, quals=1)
    assert toy_index_scan_cost(100) < seq / 50
    assert toy_index_scan_cost(100_000) > seq


def test_lowering_random_page_cost_moves_the_crossover_right():
    hdd = crossover_fraction(16_394, 1_000_000, random_page_cost=4.0)
    ssd = crossover_fraction(16_394, 1_000_000, random_page_cost=1.1)
    assert hdd == pytest.approx(0.0072, abs=0.0001)
    assert ssd == pytest.approx(0.0259, abs=0.0001)
    assert ssd > 3 * hdd

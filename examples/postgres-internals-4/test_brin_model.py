"""BRIN pruning depends on physical order, range size and summarization."""

import random

from brin_model import pages_to_read, summarize

N_PAGES, ROWS_PER_PAGE = 12_800, 100
# an append-only event log: created_at (seconds) grows with physical position
SORTED = [[p * ROWS_PER_PAGE + i for i in range(ROWS_PER_PAGE)] for p in range(N_PAGES)]
ONE_HOUR = (500_000, 503_600)


def test_correlated_column_reads_a_tiny_fraction():
    summary = summarize(SORTED, 128)
    assert len(summary) == 100  # 12,800 pages / 128 pages per range
    read = pages_to_read(summary, *ONE_HOUR, 128, N_PAGES)
    assert len(read) == 128  # one range out of 100


def test_smaller_ranges_mean_bigger_index_but_fewer_pages():
    summary = summarize(SORTED, 16)
    assert len(summary) == 800
    assert len(pages_to_read(summary, *ONE_HOUR, 16, N_PAGES)) == 48


def test_shuffled_rows_make_brin_useless():
    values = [v for p in SORTED for v in p]
    random.Random(7).shuffle(values)
    shuffled = [values[i : i + ROWS_PER_PAGE] for i in range(0, len(values), ROWS_PER_PAGE)]
    read = pages_to_read(summarize(shuffled, 128), *ONE_HOUR, 128, N_PAGES)
    assert len(read) == N_PAGES  # every range's min..max spans the hour


def test_unsummarized_ranges_are_always_read():
    summary = summarize(SORTED, 128, summarized_pages=12_160)  # last 5 ranges are new
    read = pages_to_read(summary, *ONE_HOUR, 128, N_PAGES)
    assert len(read) == 128 + 5 * 128

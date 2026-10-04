"""Leftmost-prefix behaviour and skip scan, on a 10,000-row payments index."""

from leftmost import build, search, skip_scan

STATUSES = ["captured", "failed", "pending", "refunded"]
ROWS = [
    {"ctid": (n // 50, n % 50 + 1), "merchant_id": n % 5, "status": STATUSES[n % 4]} for n in range(10000)
]
INDEX = build(ROWS, ["merchant_id", "status"])


def test_entries_are_sorted_by_key_then_ctid():
    assert sorted(INDEX) == INDEX
    assert INDEX[0] == ((0, "captured"), (0, 1))


def test_leading_column_condition_reads_one_contiguous_slice():
    hits = search(INDEX, (3,))
    assert len(hits) == 2_000  # only merchant 3's entries, nothing else
    assert all(key[0] == 3 for key, _ in hits)


def test_both_columns_narrow_the_slice_further():
    assert len(search(INDEX, (3, "pending"))) == 500


def test_second_column_alone_has_no_single_slice():
    # status = 'pending' entries sit inside every merchant's block, so one search can't find them
    positions = [i for i, (key, _) in enumerate(INDEX) if key[1] == "pending"]
    assert positions[-1] - positions[0] > len(INDEX) // 2


def test_skip_scan_does_one_search_per_leading_value():
    found, searches = skip_scan(INDEX, "pending")
    assert searches == 5
    assert len(found) == 2_500


def test_skip_scan_gets_expensive_with_many_leading_values():
    rows = [{"ctid": (n, 1), "merchant_id": n, "status": "pending"} for n in range(4_000)]
    _, searches = skip_scan(build(rows, ["merchant_id", "status"]), "pending")
    assert searches == 4_000  # one search per row: no better than reading everything

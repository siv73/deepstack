"""Every number the page quotes from row_cost.py.

The expected values were also checked against pageinspect's lp_len on a real
64-bit PostgreSQL server when the page was written.
"""

from row_cost import pack_columns, row_size, rows_per_page

BAD = [
    ("paid", "boolean"),
    ("user_id", "bigint"),
    ("refunded", "boolean"),
    ("amount_paise", "bigint"),
    ("gift", "boolean"),
    ("created_at", "timestamptz"),
]


def as_values(cols):
    return [(t, 1) for _, t in cols]


def test_padded_order_costs_72_bytes_and_107_rows_per_page():
    assert row_size(as_values(BAD)) == 72
    assert rows_per_page(72) == 107


def test_packed_order_costs_51_bytes_and_136_rows_per_page():
    packed = pack_columns(BAD)
    assert [t for _, t in packed] == ["bigint", "bigint", "timestamptz", "boolean", "boolean", "boolean"]
    assert row_size(as_values(packed)) == 51
    assert rows_per_page(51) == 136


def test_null_bitmap_fits_in_header_padding_up_to_8_columns():
    no_null = [("integer", 1), ("integer", 1), ("text", 1)]
    with_null = [("integer", 1), ("integer", None), ("text", 1)]
    assert row_size(no_null) == 34
    assert row_size(with_null) == 30  # bitmap byte sits in the 24th header byte


def test_ninth_column_makes_the_bitmap_cost_8_bytes():
    nine = [("integer", 1)] * 8 + [("integer", None)]
    assert row_size(nine) == 32 + 8 * 4


def test_short_text_uses_1_byte_header_long_text_4():
    assert row_size([("text", 126)]) == 24 + 127
    assert row_size([("text", 127)]) == 24 + 131


def test_empty_row_gives_the_291_rows_per_page_ceiling():
    assert row_size([]) == 24
    assert rows_per_page(row_size([])) == 291

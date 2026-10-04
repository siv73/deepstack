"""Estimate how many bytes a heap row takes on an 8 kB PostgreSQL page.

Covers inline (not TOASTed) values on a 64-bit server where MAXALIGN is 8.
"""

import math

PAGE = 8192
PAGE_HEADER = 24  # PageHeaderData
LINE_POINTER = 4  # one ItemIdData per row
ROW_HEADER = 23  # HeapTupleHeaderData, before the null bitmap
MAXALIGN = 8

# type -> (length in bytes, alignment in bytes); length None = variable (varlena)
TYPES = {
    "boolean": (1, 1),
    "smallint": (2, 2),
    "integer": (4, 4),
    "date": (4, 4),
    "bigint": (8, 8),
    "double precision": (8, 8),
    "timestamptz": (8, 8),
    "uuid": (16, 1),
    "text": (None, 4),
}


def align(offset: int, to: int) -> int:
    return math.ceil(offset / to) * to


def varlena_size(nbytes: int) -> tuple[int, int]:
    """(stored size, alignment) of an inline variable-length value of nbytes."""
    if nbytes + 1 <= 127:
        return nbytes + 1, 1  # 1-byte header, no alignment padding
    return nbytes + 4, 4  # 4-byte header, int-aligned


def row_size(columns: list[tuple[str, int | None]]) -> int:
    """Bytes of one row. columns = [(type, value_bytes or None for NULL)]."""
    has_null = any(v is None for _, v in columns)
    bitmap = math.ceil(len(columns) / 8) if has_null else 0
    offset = align(ROW_HEADER + bitmap, MAXALIGN)  # t_hoff: where column data starts
    for type_name, value in columns:
        if value is None:
            continue  # NULLs take no data bytes, only a bit in the bitmap
        length, alignment = TYPES[type_name]
        if length is None:
            length, alignment = varlena_size(value)
        offset = align(offset, alignment) + length
    return offset


def rows_per_page(row_bytes: int) -> int:
    """Rows that fit on one page: each needs its MAXALIGNed row plus a line pointer."""
    return (PAGE - PAGE_HEADER) // (align(row_bytes, MAXALIGN) + LINE_POINTER)


def pack_columns(columns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Reorder (name, type) pairs: widest alignment first, variable-length last."""

    def key(col):
        length, alignment = TYPES[col[1]]
        return (length is None, -alignment, -(length or 0))

    return sorted(columns, key=key)

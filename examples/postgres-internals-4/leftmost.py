"""A multicolumn B-tree modelled as a sorted list of (key, ctid) entries."""

from bisect import bisect_left


def build(rows, cols):
    """Key columns in index order; the ctid breaks ties between equal keys."""
    return sorted((tuple(r[c] for c in cols), r["ctid"]) for r in rows)


def search(index, prefix):
    """One index search: jump to the first key starting with prefix, read while it matches."""
    i = bisect_left(index, (prefix,))
    out = []
    while i < len(index) and index[i][0][: len(prefix)] == prefix:
        out.append(index[i])
        i += 1
    return out


def skip_scan(index, later_value):
    """No condition on column 1: one search per distinct leading value (PG18 skip scan)."""
    leading = sorted({key[0] for key, _ in index})
    found = [e for v in leading for e in search(index, (v, later_value))]
    return found, len(leading)

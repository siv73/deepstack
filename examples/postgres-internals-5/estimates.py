"""Row estimates the way the PostgreSQL planner makes them, for one column at a time."""

from dataclasses import dataclass, field


@dataclass
class ColumnStats:
    """What ANALYZE leaves in pg_stats for one column."""

    null_frac: float = 0.0
    n_distinct: float = -1.0  # > 0: a count; < 0: minus the fraction of rows that are distinct
    mcv: dict = field(default_factory=dict)  # most_common_vals -> most_common_freqs
    histogram: list = field(default_factory=list)  # histogram_bounds, MCVs excluded


def distinct_values(s: ColumnStats, rows: float) -> float:
    return s.n_distinct if s.n_distinct > 0 else -s.n_distinct * rows


def eq_sel(s: ColumnStats, value, rows: float) -> float:
    """col = value: the MCV frequency, or an even share of what the MCVs leave over."""
    if value in s.mcv:
        return s.mcv[value]
    others = distinct_values(s, rows) - len(s.mcv)
    return (1 - sum(s.mcv.values()) - s.null_frac) / others


def hist_lt_fraction(bounds: list, value) -> float:
    """Share of the histogram below value: whole buckets plus a straight-line part of one."""
    if value <= bounds[0]:
        return 0.0
    if value >= bounds[-1]:
        return 1.0
    buckets = len(bounds) - 1
    for i in range(buckets):
        lo, hi = bounds[i], bounds[i + 1]
        if lo <= value < hi:
            return (i + (value - lo) / (hi - lo)) / buckets
    return 1.0


def lt_sel(s: ColumnStats, value) -> float:
    """col < value: exact over the MCVs, histogram over the rest."""
    mcv_part = sum(f for v, f in s.mcv.items() if v < value)
    rest = 1 - sum(s.mcv.values()) - s.null_frac
    return mcv_part + hist_lt_fraction(s.histogram, value) * rest


def and_sel(*sels: float) -> float:
    """Without extended statistics, conditions are assumed independent: multiply."""
    out = 1.0
    for x in sels:
        out *= x
    return out


def dependent_and_sel(p_a: float, p_b: float, degree: float) -> float:
    """With a functional-dependency statistic of the given degree (dependencies.c)."""
    return degree * min(p_a, p_b) + (1 - degree) * p_a * p_b


def unique_join_sel(rows1: float, rows2: float, null1: float = 0.0, null2: float = 0.0) -> float:
    """Equality join on two columns with no MCVs where every value is distinct."""
    return (1 - null1) * (1 - null2) / max(rows1, rows2)


def estimate(rows: float, sel: float) -> int:
    return round(rows * sel)

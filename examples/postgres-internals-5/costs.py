"""Planner cost units, and a toy model of where an index scan stops paying."""

SEQ_PAGE_COST = 1.0  # PostgreSQL 18 defaults
RANDOM_PAGE_COST = 4.0
CPU_TUPLE_COST = 0.01
CPU_INDEX_TUPLE_COST = 0.005
CPU_OPERATOR_COST = 0.0025


def seq_scan_cost(pages, rows, quals=0, seq_page_cost=SEQ_PAGE_COST):
    """The planner's formula: every page read in order, every row processed, every condition checked."""
    return pages * seq_page_cost + rows * (CPU_TUPLE_COST + quals * CPU_OPERATOR_COST)


def toy_index_scan_cost(matching_rows, random_page_cost=RANDOM_PAGE_COST):
    """Worst case: each matching row is on a different, uncached page. Not the planner's formula."""
    per_row = random_page_cost + CPU_INDEX_TUPLE_COST + CPU_TUPLE_COST
    return matching_rows * per_row


def crossover_fraction(pages, rows, random_page_cost=RANDOM_PAGE_COST):
    """Fraction of the table above which the toy index scan costs more than a sequential scan."""
    seq = seq_scan_cost(pages, rows, quals=1)
    return seq / toy_index_scan_cost(rows, random_page_cost)

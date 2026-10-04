"""The model reproduces the worked estimates in the PostgreSQL 18 docs (chapter "Row Estimation Examples")."""

import pytest
from estimates import (
    ColumnStats,
    and_sel,
    dependent_and_sel,
    eq_sel,
    estimate,
    lt_sel,
    unique_join_sel,
)

ROWS = 10_000
UNIQUE1 = ColumnStats(n_distinct=-1, histogram=[0, 993, 1997, 3050, 4040, 5036, 5957, 7057, 8029, 9016, 9995])
STRINGU1 = ColumnStats(
    n_distinct=676,
    mcv={"EJAAAA": 0.00333333, **{v: 0.003 for v in ["BB", "CR", "FC", "FE", "GS", "JO", "MC", "NA", "WG"]}},
)


def test_range_uses_the_histogram():
    sel = lt_sel(UNIQUE1, 1000)
    assert sel == pytest.approx(0.100697, abs=1e-6)
    assert estimate(ROWS, sel) == 1007


def test_range_in_the_first_bucket():
    assert estimate(ROWS, lt_sel(UNIQUE1, 50)) == 50


def test_equality_on_a_common_value_uses_its_frequency():
    assert estimate(ROWS, eq_sel(STRINGU1, "CR", ROWS)) == 30


def test_equality_on_a_rare_value_shares_out_the_rest():
    sel = eq_sel(STRINGU1, "xxx", ROWS)
    assert sel == pytest.approx(0.0014559, rel=1e-4)
    assert estimate(ROWS, sel) == 15


def test_two_conditions_are_multiplied():
    sel = and_sel(lt_sel(UNIQUE1, 1000), eq_sel(STRINGU1, "xxx", ROWS))
    assert estimate(ROWS, sel) == 1


def test_correlated_columns_are_underestimated_a_hundredfold():
    # a and b always hold the same value, 100 values, 1% each
    a = b = ColumnStats(n_distinct=100, mcv={v: 0.01 for v in range(100)})
    independent = estimate(ROWS, and_sel(eq_sel(a, 1, ROWS), eq_sel(b, 1, ROWS)))
    assert independent == 1  # the real answer is 100
    with_dependency = estimate(ROWS, dependent_and_sel(0.01, 0.01, degree=1.0))
    assert with_dependency == 100


def test_join_of_two_unique_columns():
    sel = unique_join_sel(10_000, 10_000)
    assert sel == pytest.approx(0.0001)
    assert estimate(50 * 10_000, sel) == 50

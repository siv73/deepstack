"""Headroom numbers used on the page."""

from wraparound import days_left, milestones


def test_milestones_with_defaults():
    m = milestones()
    assert m["forced autovacuum"] == 200_000_000
    assert m["failsafe"] == 1_600_000_000
    assert m["warnings"] == 2_107_483_647
    assert m["writes refused"] == 2_144_483_647


def test_failsafe_never_below_105_percent_of_freeze_max_age():
    assert milestones(freeze_max_age=2_000_000_000)["failsafe"] == 2_100_000_000


def test_ten_times_the_write_rate_turns_weeks_into_days():
    calm = days_left(150_000_000, xids_per_day=50_000_000)
    busy = days_left(150_000_000, xids_per_day=500_000_000)
    assert calm["forced autovacuum"] == 1.0
    assert round(calm["writes refused"], 1) == 39.9
    assert round(busy["writes refused"], 1) == 4.0
    assert busy["forced autovacuum"] == 0.1


def test_past_a_milestone_reports_zero():
    assert days_left(300_000_000, 10_000_000)["forced autovacuum"] == 0.0

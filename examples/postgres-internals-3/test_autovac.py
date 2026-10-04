"""The numbers the page quotes for autovacuum's trigger and throttle."""

from autovac import Settings, dead_row_trigger, insert_trigger, pages_per_second


def test_ten_million_rows_wait_for_two_million_dead():
    assert dead_row_trigger(10_000_000) == 2_000_050


def test_big_tables_are_capped_at_one_hundred_million():
    assert dead_row_trigger(1_000_000_000) == 100_000_000
    assert dead_row_trigger(1_000_000_000, Settings(max_threshold=-1)) == 200_000_050


def test_per_table_tuning_for_a_hot_table():
    hot = Settings(scale_factor=0.01, threshold=1000)
    assert dead_row_trigger(50_000_000) == 10_000_050
    assert dead_row_trigger(50_000_000, hot) == 501_000


def test_insert_trigger_counts_only_the_unfrozen_part():
    assert insert_trigger(10_000_000, relpages=100_000, relallfrozen=50_000) == 1_001_000
    assert insert_trigger(10_000_000, 100_000, 0, Settings(insert_threshold=-1)) == float("inf")


def test_throttle_budget():
    # page read from disk (miss = 2): at most 50,000 pages a second
    assert pages_per_second() == 50_000
    # page read from disk and dirtied (2 + 20): about 4,500 pages a second
    assert round(pages_per_second(cost_per_page=22)) == 4545
    # three workers share one budget of 200, so together they are no faster
    per_worker = pages_per_second(cost_limit=200 / 3, cost_per_page=22)
    assert round(3 * per_worker) == 4545
    # raising the limit to 2000 gives ten times the budget
    assert round(pages_per_second(cost_limit=2000, cost_per_page=22)) == 45455

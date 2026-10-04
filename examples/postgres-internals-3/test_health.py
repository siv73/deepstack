"""The diagnoses the page draws from real-looking statistics rows."""

from health import bloat_report, hot_report


def row(name, upd, hot, newpage):
    return {"relname": name, "n_tup_upd": upd, "n_tup_hot_upd": hot, "n_tup_newpage_upd": newpage}


def test_small_transactions_with_room_are_hot():
    assert hot_report(row("wallets", 80_000, 78_856, 1_144)) == "wallets: 99% HOT, fine"


def test_full_pages_push_versions_to_new_pages():
    assert hot_report(row("orders", 100_000, 10_782, 89_218)).endswith("lower fillfactor")


def test_index_on_updated_column_kills_hot():
    # updates fit on the page (few new-page updates) but none are HOT
    assert hot_report(row("sessions", 40_000, 0, 3_000)).endswith("check indexes")


def test_too_few_updates():
    assert hot_report(row("tiny", 50, 0, 50)).endswith("too few updates to judge")


def test_bloat_reports():
    assert bloat_report({"dead_tuple_percent": 38.4, "free_percent": 0.4}).startswith("dead rows")
    assert bloat_report({"dead_tuple_percent": 0.0, "free_percent": 94.7}).startswith("mostly empty")
    assert bloat_report({"dead_tuple_percent": 2.0, "free_percent": 12.0}).startswith("fine")

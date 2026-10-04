"""The audit's verdicts on a realistic payments schema."""

from index_audit import audit


def ix(name, cols, scans, unique=False, table="payments"):
    return {"name": name, "table": table, "columns": cols, "unique": unique, "idx_scan": scans}


SCHEMA = [
    ix("payments_pkey", ("id",), 0, unique=True),
    ix("payments_merchant", ("merchant_id",), 91_000),
    ix("payments_merchant_created", ("merchant_id", "created_at"), 4_200_000),
    ix("payments_old_report", ("currency", "amount"), 0),
    ix("refunds_merchant", ("merchant_id",), 0, table="refunds"),
]


def test_unique_index_is_never_flagged():
    assert not any(n.startswith("payments_pkey") for n in audit(SCHEMA, 90))


def test_unused_index_is_flagged():
    assert "payments_old_report: never scanned; check replicas, then drop" in audit(SCHEMA, 90)


def test_prefix_of_a_wider_index_is_flagged_even_when_used():
    notes = audit(SCHEMA, 90)
    assert "payments_merchant: leading columns of payments_merchant_created; likely redundant" in notes


def test_other_tables_are_not_compared():
    assert not any("refunds_merchant: leading" in n for n in audit(SCHEMA, 90))


def test_fresh_counters_give_no_verdict():
    assert audit(SCHEMA, 3) == ["counters too young to judge: they were reset recently"]

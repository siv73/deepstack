"""The generic-plan switch after five executions, and why it can hurt one hot value."""

from plan_cache import PreparedStatement, planning_charge

# Per-merchant query. Merchant 1 owns most rows: its best plan is a sequential scan.
SEQ_SCAN, INDEX_SMALL = 11_677.0, 82.0
GENERIC_INDEX = 691.0  # one plan for "some merchant": an index scan sized for an average merchant


def custom(merchant):
    return SEQ_SCAN if merchant == 1 else INDEX_SMALL


def test_first_five_executions_are_custom_then_generic_wins():
    stmt = PreparedStatement(custom, GENERIC_INDEX)
    plans = [stmt.execute(m) for m in (1, 7, 8, 9, 10, 11, 12)]
    assert plans[:5] == ["custom"] * 5
    # average custom cost is inflated by merchant 1, so the generic plan looks cheaper
    assert plans[5:] == ["generic", "generic"]


def test_once_generic_wins_it_also_serves_the_hot_merchant():
    stmt = PreparedStatement(custom, GENERIC_INDEX)
    for m in (1, 7, 8, 9, 10):
        stmt.execute(m)
    assert stmt.execute(1) == "generic"  # an index scan over most of the table


def test_small_merchants_only_keep_custom_plans():
    stmt = PreparedStatement(custom, GENERIC_INDEX)
    plans = [stmt.execute(m) for m in range(2, 12)]
    assert set(plans) == {"custom"}  # generic (691) never beats about 82 + planning charge


def test_force_custom_plan_replans_every_time():
    stmt = PreparedStatement(custom, GENERIC_INDEX, mode="force_custom_plan")
    assert {stmt.execute(m) for m in (1, 7, 8, 9, 10, 11, 1)} == {"custom"}


def test_planning_charge_grows_with_relations():
    assert planning_charge(1) == 5.0
    assert planning_charge(5) == 15.0

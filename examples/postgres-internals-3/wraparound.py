"""How many days of transaction IDs are left before each wraparound milestone."""

WRAP_AGE = 2**31 - 1  # varsup.c: wrap limit = oldest datfrozenxid + (MaxTransactionId >> 1)


def milestones(freeze_max_age=200_000_000, failsafe_age=1_600_000_000) -> dict[str, int]:
    """Ages at which PostgreSQL 18 changes behaviour (defaults shown)."""
    return {
        "forced autovacuum": freeze_max_age,
        "failsafe": max(failsafe_age, int(1.05 * freeze_max_age)),
        "warnings": WRAP_AGE - 40_000_000,
        "writes refused": WRAP_AGE - 3_000_000,
    }


def days_left(age_now: int, xids_per_day: int, **settings) -> dict[str, float]:
    return {name: max(0.0, (age - age_now) / xids_per_day) for name, age in milestones(**settings).items()}

"""When autovacuum picks a table, and how fast cost throttling lets it work (PostgreSQL 18)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    threshold: int = 50  # autovacuum_vacuum_threshold
    scale_factor: float = 0.2  # autovacuum_vacuum_scale_factor
    max_threshold: int = 100_000_000  # autovacuum_vacuum_max_threshold; -1 = no cap
    insert_threshold: int = 1000  # autovacuum_vacuum_insert_threshold; -1 = off
    insert_scale_factor: float = 0.2  # autovacuum_vacuum_insert_scale_factor


PG18 = Settings()


def dead_row_trigger(reltuples: float, s: Settings = PG18) -> float:
    t = s.threshold + s.scale_factor * reltuples
    return t if s.max_threshold == -1 else min(s.max_threshold, t)


def insert_trigger(reltuples: float, relpages: int, relallfrozen: int, s: Settings = PG18) -> float:
    if s.insert_threshold == -1:
        return float("inf")
    not_frozen = 1 - relallfrozen / relpages if relpages else 1.0
    return s.insert_threshold + s.insert_scale_factor * reltuples * not_frozen


def pages_per_second(cost_limit=200, delay_ms=2.0, cost_per_page=2):
    """Upper bound: at most cost_limit units of work between sleeps of delay_ms."""
    return cost_limit / cost_per_page * (1000 / delay_ms)

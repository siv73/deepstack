"""Two health checks built on pg_stat_user_tables and pgstattuple rows."""


def hot_report(row: dict) -> str:
    """row: relname, n_tup_upd, n_tup_hot_upd, n_tup_newpage_upd from pg_stat_user_tables."""
    upd = row["n_tup_upd"]
    if upd < 10_000:
        return f"{row['relname']}: too few updates to judge"
    hot = row["n_tup_hot_upd"] / upd
    newpage = row["n_tup_newpage_upd"] / upd
    if hot >= 0.9:
        return f"{row['relname']}: {hot:.0%} HOT, fine"
    if newpage > 0.5:
        return f"{row['relname']}: {hot:.0%} HOT, page full: lower fillfactor"
    return f"{row['relname']}: {hot:.0%} HOT, indexed column changes: check indexes"


def bloat_report(st: dict) -> str:
    """st: one pgstattuple() row."""
    if st["dead_tuple_percent"] > 20:
        return "dead rows: VACUUM, then find what held it back"
    if st["free_percent"] > 50:
        return "mostly empty pages: rewrite (pg_repack) if it will not regrow"
    return "fine: free space is being reused"

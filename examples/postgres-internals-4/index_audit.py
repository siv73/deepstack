"""Flag indexes that cost writes but never help reads."""


def audit(indexes, stats_age_days):
    """indexes: dicts with name, table, columns (tuple), unique, idx_scan (pg_stat_user_indexes)."""
    if stats_age_days < 30:
        return ["counters too young to judge: they were reset recently"]
    notes = []
    for ix in indexes:
        if ix["unique"]:
            continue  # it enforces a constraint even with zero scans
        if ix["idx_scan"] == 0:
            notes.append(f"{ix['name']}: never scanned; check replicas, then drop")
        for other in indexes:
            n = len(ix["columns"])
            same_table = other is not ix and other["table"] == ix["table"]
            if same_table and len(other["columns"]) > n and other["columns"][:n] == ix["columns"]:
                notes.append(f"{ix['name']}: leading columns of {other['name']}; likely redundant")
    return notes

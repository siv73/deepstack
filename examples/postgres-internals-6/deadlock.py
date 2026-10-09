"""A deadlock is a cycle in who-waits-for-whom. PostgreSQL looks for one only after a session
has waited deadlock_timeout (1s by default), then aborts one transaction in the cycle."""


def find_cycle(waits_for: dict[str, str]) -> list[str] | None:
    """waits_for maps each waiting transaction to the one holding the lock it wants."""
    for start in waits_for:
        path, tx = [], start
        while tx in waits_for and tx not in path:
            path.append(tx)
            tx = waits_for[tx]
        if tx in path:
            return path[path.index(tx) :]
    return None


def run_transfers(plans: dict[str, list[int]]) -> dict[str, str]:
    """Each transaction locks its rows in list order, one step at a time, side by side."""
    holder, waits_for = {}, {}
    for step in range(max(len(rows) for rows in plans.values())):
        for tx, rows in plans.items():
            if tx in waits_for or step >= len(rows):
                continue
            owner = holder.setdefault(rows[step], tx)
            if owner != tx:
                waits_for[tx] = owner
    return waits_for

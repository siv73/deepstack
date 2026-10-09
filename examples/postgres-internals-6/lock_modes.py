"""Table-level lock conflicts (PostgreSQL 18 docs, Table 13.2) and the mode common commands take."""

MODES = [
    "ACCESS SHARE",
    "ROW SHARE",
    "ROW EXCLUSIVE",
    "SHARE UPDATE EXCLUSIVE",
    "SHARE",
    "SHARE ROW EXCLUSIVE",
    "EXCLUSIVE",
    "ACCESS EXCLUSIVE",
]  # weakest to strongest
AS, RS, RE, SUE, S, SRE, E, AE = MODES
CONFLICTS = {  # each row is one line of the docs' conflict table
    AS: {AE},
    RS: {E, AE},
    RE: {S, SRE, E, AE},
    SUE: {SUE, S, SRE, E, AE},
    S: {RE, SUE, SRE, E, AE},
    SRE: {RE, SUE, S, SRE, E, AE},
    E: {RS, RE, SUE, S, SRE, E, AE},
    AE: set(MODES),
}

COMMAND_LOCK = {
    "SELECT": "ACCESS SHARE",
    "SELECT ... FOR UPDATE": "ROW SHARE",
    "INSERT / UPDATE / DELETE": "ROW EXCLUSIVE",
    "VACUUM / ANALYZE": "SHARE UPDATE EXCLUSIVE",
    "CREATE INDEX CONCURRENTLY": "SHARE UPDATE EXCLUSIVE",
    "CREATE INDEX": "SHARE",
    "ALTER TABLE ... ADD FOREIGN KEY": "SHARE ROW EXCLUSIVE",
    "ALTER TABLE (most forms)": "ACCESS EXCLUSIVE",
    "TRUNCATE / DROP TABLE / VACUUM FULL": "ACCESS EXCLUSIVE",
}


def conflicts(a: str, b: str) -> bool:
    """True if a lock in mode a and a lock in mode b can't be held on one table by two transactions."""
    return b in CONFLICTS[a]


def blocks(holder_cmd: str, waiter_cmd: str) -> bool:
    return conflicts(COMMAND_LOCK[holder_cmd], COMMAND_LOCK[waiter_cmd])

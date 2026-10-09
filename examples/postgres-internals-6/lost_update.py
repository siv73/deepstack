"""Two buyers race for the last unit of stock, under the PostgreSQL 18 rules for a row
that another transaction changed first (docs 13.2.1 and 13.2.2).

Simplification: each UPDATE commits at once, so "waiting for the first updater" is already over.
"""


class SerializationFailure(Exception):
    sqlstate = "40001"


class Row:
    def __init__(self, value):
        self.value, self.version = value, 0  # version goes up on every committed change


class Tx:
    def __init__(self, row, level="read committed"):
        self.row, self.level, self.snap = row, level, None

    def _statement_snapshot(self):
        if self.level == "read committed" or self.snap is None:  # RC: new snapshot per statement
            self.snap = (self.row.value, self.row.version)  # RR: one snapshot, at the first statement

    def select(self):
        self._statement_snapshot()
        return self.snap[0]

    def update(self, set_to=None, add=0, where=lambda v: True) -> int:
        """Returns the number of rows changed (0 or 1)."""
        self._statement_snapshot()
        if self.row.version != self.snap[1]:  # someone committed a change after our snapshot
            raise SerializationFailure("could not serialize access due to concurrent update")
        if not where(self.row.value):  # the WHERE clause is checked on the latest version
            return 0
        self.row.value = set_to if set_to is not None else self.row.value + add
        self.row.version += 1
        return 1

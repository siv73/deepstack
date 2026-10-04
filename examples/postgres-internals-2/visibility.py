"""A small model of PostgreSQL's MVCC visibility check for one row version.

Simplified on purpose: it ignores command ids inside a transaction,
subtransactions, and xmax values set only by row locks.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    xmin: int  # lowest transaction id still running when the snapshot was taken
    xmax: int  # one past the highest finished transaction id
    xip: frozenset[int]  # transaction ids running when the snapshot was taken

    @classmethod
    def parse(cls, text: str) -> "Snapshot":
        """Parse pg_current_snapshot() output, e.g. '10:20:10,14,15'."""
        xmin, xmax, xip = text.split(":")
        return cls(int(xmin), int(xmax), frozenset(int(x) for x in xip.split(",") if x))

    def finished(self, xid: int) -> bool:
        """Had this transaction finished (committed or aborted) when the snapshot was taken?"""
        return xid < self.xmin or (xid < self.xmax and xid not in self.xip)


@dataclass(frozen=True)
class RowVersion:
    xmin: int  # transaction that inserted this version
    xmax: int = 0  # transaction that deleted or replaced it; 0 = none


def is_visible(v: RowVersion, snap: Snapshot, status: dict[int, str], me: int | None = None) -> bool:
    """status maps xid -> 'committed' | 'aborted' | 'in progress' (what pg_xact says now)."""

    def committed_for_me(xid: int) -> bool:
        return snap.finished(xid) and status.get(xid) == "committed"

    inserted = v.xmin == me or committed_for_me(v.xmin)
    if not inserted:
        return False
    if v.xmax == 0:
        return True
    if v.xmax == me:
        return False  # I deleted or replaced it myself
    return not committed_for_me(v.xmax)

"""Every scenario the page walks through, in the model.

The transaction ids (926, 927) and snapshot text come from a real session
that UPDATEd one row and was then rolled back.
"""

from visibility import RowVersion, Snapshot, is_visible

OLD = RowVersion(xmin=926, xmax=927)  # balance 100, replaced by transaction 927
NEW = RowVersion(xmin=927)  # balance 50, written by transaction 927


def visible(snap, status, me=None):
    return [v for v in (OLD, NEW) if is_visible(v, snap, status, me)]


def test_snapshot_text_follows_the_docs_example():
    s = Snapshot.parse("10:20:10,14,15")
    assert (s.xmin, s.xmax, s.xip) == (10, 20, frozenset({10, 14, 15}))
    assert s.finished(9) and s.finished(12)
    assert not s.finished(14) and not s.finished(20)


def test_while_927_runs_others_see_old_and_927_sees_new():
    status = {926: "committed", 927: "in progress"}
    other = Snapshot.parse("927:927:")
    assert visible(other, status) == [OLD]
    assert visible(other, status, me=927) == [NEW]


def test_after_rollback_everyone_sees_old_even_though_xmax_is_set():
    status = {926: "committed", 927: "aborted"}
    assert visible(Snapshot.parse("928:928:"), status) == [OLD]
    assert OLD.xmax != 0


def test_after_commit_new_snapshots_see_new():
    status = {926: "committed", 927: "committed"}
    assert visible(Snapshot.parse("928:928:"), status) == [NEW]


def test_snapshot_taken_before_the_commit_keeps_seeing_old():
    status = {926: "committed", 927: "committed"}
    taken_earlier = Snapshot.parse("927:927:")  # taken while 927 was still running
    assert visible(taken_earlier, status) == [OLD]

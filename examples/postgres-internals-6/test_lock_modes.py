"""The conflict table matches the PostgreSQL 18 docs (13.3.1 Table-Level Locks)."""

import pytest
from lock_modes import COMMAND_LOCK, MODES, blocks, conflicts


@pytest.mark.parametrize("a", MODES)
@pytest.mark.parametrize("b", MODES)
def test_conflicts_are_symmetric(a, b):
    assert conflicts(a, b) == conflicts(b, a)


def test_access_share_conflicts_only_with_access_exclusive():
    assert [m for m in MODES if conflicts("ACCESS SHARE", m)] == ["ACCESS EXCLUSIVE"]


def test_access_exclusive_conflicts_with_all_eight():
    assert all(conflicts("ACCESS EXCLUSIVE", m) for m in MODES)


def test_row_exclusive_does_not_conflict_with_itself():
    assert not conflicts("ROW EXCLUSIVE", "ROW EXCLUSIVE")  # many writers share one table
    assert conflicts("SHARE UPDATE EXCLUSIVE", "SHARE UPDATE EXCLUSIVE")  # one VACUUM per table


def test_only_access_exclusive_commands_block_a_plain_select():
    blockers = {cmd for cmd in COMMAND_LOCK if blocks(cmd, "SELECT")}
    assert {COMMAND_LOCK[c] for c in blockers} == {"ACCESS EXCLUSIVE"}


def test_create_index_blocks_writes_but_not_reads_and_concurrently_blocks_neither():
    assert blocks("CREATE INDEX", "INSERT / UPDATE / DELETE")
    assert not blocks("CREATE INDEX", "SELECT")
    assert not blocks("CREATE INDEX CONCURRENTLY", "INSERT / UPDATE / DELETE")


def test_adding_a_foreign_key_blocks_writes_but_not_reads():
    assert blocks("ALTER TABLE ... ADD FOREIGN KEY", "INSERT / UPDATE / DELETE")
    assert not blocks("ALTER TABLE ... ADD FOREIGN KEY", "SELECT")

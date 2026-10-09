"""A waiting ALTER TABLE blocks every later reader, and lock_timeout lets them through."""

from lock_queue import TableLocks


def migration_behind_a_long_report():
    t = TableLocks()
    assert t.request("report", "SELECT") == "granted"  # a 10-minute analytics query
    assert t.request("migration", "ALTER TABLE (most forms)") == "waiting"  # needs ACCESS EXCLUSIVE
    return t


def test_readers_queue_behind_the_waiting_migration():
    t = migration_behind_a_long_report()
    assert t.request("api-1", "SELECT") == "waiting"
    assert t.request("api-2", "SELECT") == "waiting"
    assert t.blocking_pids("migration") == ["report"]  # hard block
    assert t.blocking_pids("api-1") == ["migration"]  # soft block: queued ahead of it


def test_lock_timeout_cancels_the_migration_and_releases_the_queue():
    t = migration_behind_a_long_report()
    t.request("api-1", "SELECT")
    t.finish("migration")  # lock_timeout fired: the ALTER gives up, to be retried later
    assert t.queue == []
    assert ("api-1", "ACCESS SHARE") in t.held


def test_when_the_report_ends_the_migration_runs_alone_first():
    t = migration_behind_a_long_report()
    t.request("api-1", "SELECT")
    t.finish("report")
    assert [s for s, _ in t.held] == ["migration"]
    assert [s for s, _ in t.queue] == ["api-1"]  # still waits until the migration commits


def test_adding_a_foreign_key_queues_writers_but_not_readers():
    t = TableLocks()
    t.request("writer", "INSERT / UPDATE / DELETE")
    assert t.request("migration", "ALTER TABLE ... ADD FOREIGN KEY") == "waiting"
    assert t.request("api-read", "SELECT") == "granted"
    assert t.request("api-write", "INSERT / UPDATE / DELETE") == "waiting"

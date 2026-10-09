"""The retry loop reruns the whole unit of work, only for retryable SQLSTATEs, and gives up."""

import pytest
from retry import run_transaction


class DbError(Exception):
    def __init__(self, sqlstate):
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


class StubConn:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def failing(*codes):
    calls = []

    def work(conn):
        calls.append(1)
        if len(calls) <= len(codes):
            raise DbError(codes[len(calls) - 1])
        return "done"

    return work, calls


def test_serialization_failure_and_deadlock_are_retried_from_the_top():
    conn, (work, calls) = StubConn(), failing("40001", "40P01")
    assert run_transaction(conn, work, sleep=lambda s: None) == "done"
    assert (len(calls), conn.rollbacks, conn.commits) == (3, 2, 1)


def test_other_errors_are_not_retried():
    conn, (work, calls) = StubConn(), failing("23505")  # unique_violation: may be a real bug
    with pytest.raises(DbError):
        run_transaction(conn, work, sleep=lambda s: None)
    assert len(calls) == 1


def test_gives_up_after_the_last_attempt():
    conn, (work, calls) = StubConn(), failing(*["40001"] * 9)
    with pytest.raises(DbError):
        run_transaction(conn, work, attempts=3, sleep=lambda s: None)
    assert (len(calls), conn.commits) == (3, 0)


def test_backoff_grows_and_is_jittered():
    delays = []
    conn, (work, _) = StubConn(), failing("40001", "40001", "40001")
    run_transaction(conn, work, base_delay=1.0, sleep=delays.append)
    assert len(delays) == 3
    assert all(0 <= d <= 2**i for i, d in enumerate(delays))

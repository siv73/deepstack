"""Which ways of selling the last unit oversell, and which don't."""

import pytest
from lost_update import Row, SerializationFailure, Tx


def test_read_then_write_in_read_committed_loses_an_update():
    stock = Row(1)
    a, b = Tx(stock), Tx(stock)
    seen_a, seen_b = a.select(), b.select()  # both see 1 unit
    sold = a.update(set_to=seen_a - 1) + b.update(set_to=seen_b - 1)
    assert (sold, stock.value) == (2, 0)  # two units sold, stock says 0: one sale is lost


def test_atomic_update_with_a_guard_sells_once():
    stock = Row(1)
    a, b = Tx(stock), Tx(stock)
    sold = a.update(add=-1, where=lambda v: v >= 1) + b.update(add=-1, where=lambda v: v >= 1)
    assert (sold, stock.value) == (1, 0)


def test_repeatable_read_fails_the_second_writer_and_a_retry_sees_the_truth():
    stock = Row(1)
    a, b = Tx(stock, "repeatable read"), Tx(stock, "repeatable read")
    seen_a, seen_b = a.select(), b.select()
    assert a.update(set_to=seen_a - 1) == 1
    with pytest.raises(SerializationFailure) as err:
        b.update(set_to=seen_b - 1)
    assert err.value.sqlstate == "40001"
    retry = Tx(stock, "repeatable read")  # retry the whole transaction: new snapshot
    assert retry.select() == 0  # sold out, so the app doesn't update


def test_repeatable_read_keeps_one_snapshot_read_committed_does_not():
    stock = Row(5)
    rr, rc, writer = Tx(stock, "repeatable read"), Tx(stock), Tx(stock)
    assert rr.select() == rc.select() == 5
    writer.update(add=-2)
    assert rr.select() == 5  # same snapshot for the whole transaction
    assert rc.select() == 3  # new snapshot for each statement

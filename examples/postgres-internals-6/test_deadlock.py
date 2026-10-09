"""Opposite lock order deadlocks; one global order (sorted ids) only makes one transaction wait."""

from deadlock import find_cycle, run_transfers


def test_opposite_order_is_a_cycle():
    waits = run_transfers({"T1": [11111, 22222], "T2": [22222, 11111]})
    assert waits == {"T1": "T2", "T2": "T1"}
    assert sorted(find_cycle(waits)) == ["T1", "T2"]


def test_sorted_order_means_waiting_not_deadlock():
    t1, t2 = sorted([11111, 22222]), sorted([22222, 11111])
    waits = run_transfers({"T1": t1, "T2": t2})
    assert waits == {"T2": "T1"}  # T2 queues behind T1 and runs when T1 commits
    assert find_cycle(waits) is None


def test_three_way_cycle_is_found():
    assert find_cycle({"A": "B", "B": "C", "C": "A", "D": "A"}) == ["A", "B", "C"]

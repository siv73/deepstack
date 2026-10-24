"""Part 9: every program on the page prints the output the page shows (out/<name>.txt)."""

import re
import sys

import pytest
from test_programs5 import LINUX, PY314, expected, interpreter, numbers, run, shape

EXACT = [
    "stuck_v9",
    "task_dump",
    "call_graph",
    "uvloop_run",
    "leaks",
    "lying_metrics",
    "telemetry_10x",
    "sigusr1_dump",
]
TIMED = ["debug_blind", "lag_metric", "incident_v10", "clock_demo", "flaky_time"]
TOLERANCE_MS = 60
COUNTS = {0, 1, 2, 3, 5, 10, 12, 20, 25, 30, 250, 1199, 1149, 1000}  # counts, prices and budgets, not times


@pytest.mark.skipif(not (LINUX and PY314), reason="output recorded on Linux with Python 3.14")
@pytest.mark.parametrize("name", EXACT)
def test_exact_output(name):
    assert run(name) == expected(name)


@pytest.mark.skipif(not (LINUX and PY314), reason="output recorded on Linux with Python 3.14")
@pytest.mark.parametrize("name", TIMED)
def test_timed_output_matches_within_tolerance(name):
    got, want = run(name), expected(name)
    assert shape(got) == shape(want)
    for g, w in zip(numbers(got), numbers(want), strict=True):
        if w in COUNTS and name != "clock_demo":
            assert g == w, (name, g, w)
        else:
            assert abs(g - w) <= TOLERANCE_MS, (name, g, w)


@pytest.mark.skipif(not (LINUX and PY314), reason="ps and pstree: Python 3.14 on Linux")
def test_ps_and_pstree_read_the_stuck_requests_from_outside():
    got = run("ps_demo")
    if "Operation not permitted" in got or "PermissionError" in got:
        pytest.skip("this machine does not allow reading another process (ptrace restrictions)")
    assert got == expected("ps_demo")


@pytest.mark.skipif(not (LINUX and PY314), reason="output recorded on Linux with Python 3.14")
def test_graph_bug_until_3_14_8():
    got = run("graph_bug")
    if sys.version_info < (3, 14, 8):
        assert got.splitlines()[1:] == expected("graph_bug").splitlines()[1:]
    else:  # gh-155143 and gh-156408 fixed: no stale waiter, no AttributeError
        assert "AttributeError" not in got and "format_call_graph(fill): printed" in got


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_sigusr1_dump_on_3_13_is_one_frame_per_task():
    python = interpreter("3.13")
    if python is None:
        pytest.skip("Python 3.13 is not installed here")
    assert run("sigusr1_dump", python) == expected("sigusr1_dump_3.13")


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13", "3.14"])
def test_version_probe9_on_each_installed_version(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    assert run("version_probe9", python) == expected(f"version_probe9_{version}")


def test_the_page_numbers_are_the_programs_numbers():
    stuck = expected("stuck_v9")
    assert "log lines while they wait: 0; errors or warnings: 0" in stuck
    assert "loop lag, worst in 500 ms: 0 ms" in stuck
    assert "requests in progress: 5; audit rows waiting in the queue: 3" in stuck
    assert "{'no answer after 2,000 ms': 5}" in stuck
    assert "asyncio.all_tasks(): 18 Tasks" in expected("task_dump")
    lag = expected("lag_metric")
    assert re.search(r"one 300 ms blocking call +worst lag  270 ms", lag)
    assert re.search(r"5 requests stuck on an await, 500 ms +worst lag    0 ms", lag)
    assert "302 bytes" in expected("telemetry_10x") and "4.17 TB a day" in expected("telemetry_10x")
    lies = expected("lying_metrics")
    assert "mean 280 ms; p50 <= 250 ms; p99 <= 2500 ms" in lies
    assert "answered calls only: 70 calls, p99 <= 250 ms" in lies
    assert "Answer.ms (compare() alone): 250 ms; the shopper waited: 1250 ms" in lies
    assert "average 0.25 ms; worst 300 ms" in lies

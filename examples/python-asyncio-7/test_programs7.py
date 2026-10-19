"""Part 7: every program on the page prints the output the page shows (out/<name>.txt)."""

import re
import subprocess

import pytest
from test_programs5 import HERE, LINUX, PY314, expected, interpreter, numbers, run, shape

EXACT = [
    "race_counter",
    "race_cache",
    "race_log_id",
    "lock_demo",
    "release_twice",
    "event_demo",
    "condition_demo",
    "barrier_demo",
    "context_basics",
    "context_tasks",
    "stampede",
    "request_ids",
    "bridge_demo",
    "pool_context",
    "lock_across_await",
    "deadlock",
    "context_lost",
    "herd_10x",
    "four_ways",
]
TIMED = ["wrong_thread", "gateway_v8"]  # real threads and sockets: times within 60 ms
TOLERANCE_MS = 60


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
        if w in (1, 3, 4, 7, 10, 21, 100, 113, 1099, 1149, 1199):  # counts and prices, not times
            assert g == w, (name, g, w)
        else:
            assert abs(g - w) <= TOLERANCE_MS, (name, g, w)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_gateway_v8_counts_are_exact():
    got = run("gateway_v8")
    for line in (
        "100 answered {'seller-b 1199': 100}",
        "seller calls made: {'seller-a': 1, 'seller-b': 1, 'seller-c': 1, 'seller-d': 1, 'seller-e': 1}",
        "10 answered {'seller-e 1149': 10}",
        "seller calls made: none",
        "the feed's callback returned ['applied']",
        "1 answered {'seller-e 1099': 1}",
        "fills still in flight when stop() returned: ['fill seller-e toaster-2s']",
        "[fill seller-e kettle-1l] seller_e_sdk: get_price kettle-1l",
        "[feed seller-e] gateway: price change applied: kettle-1l 1099",
        "audit rows written: 113 | background failures: none",
        "after asyncio.run returned: fill seller-e toaster-2s cancelled = True",
    ):
        assert line in got, line
    assert "'sale-*': 100" in got and "'later-*': 10" in got


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_free_threaded_build_outputs():
    python = interpreter("3.14t")
    if python is None:
        pytest.skip("free-threaded Python 3.14 is not installed here")
    assert run("pool_context", python) == expected("pool_context_ft")
    assert run("bridge_demo", python) == expected("bridge_demo_ft")


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13"])
def test_primitives_behave_the_same_on_older_versions(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    for name in (
        "race_counter",
        "race_log_id",
        "lock_demo",
        "release_twice",
        "event_demo",
        "condition_demo",
        "barrier_demo",
        "deadlock",
        "context_lost",
        "stampede",
        "wrong_thread",
    ):
        got, want = run(name, python), expected(name)
        assert shape(got) == shape(want), (version, name)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13"])
def test_token_as_context_manager_is_new_in_3_14(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    result = subprocess.run([python, "context_basics.py"], cwd=HERE, capture_output=True, text=True)
    assert result.returncode != 0
    assert "object does not support the context manager protocol" in result.stderr
    assert result.stdout == "".join(expected("context_basics").splitlines(keepends=True)[:7])


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.12", "3.13"])
def test_task_context_copies_are_the_same_from_3_12(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    assert run("context_tasks", python) == expected("context_tasks")


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_task_get_context_is_missing_on_3_11():
    python = interpreter("3.11")
    if python is None:
        pytest.skip("Python 3.11 is not installed here")
    result = subprocess.run([python, "context_tasks.py"], cwd=HERE, capture_output=True, text=True)
    assert "object has no attribute 'get_context'" in result.stderr
    assert result.stdout.splitlines() == expected("context_tasks").splitlines()[:5]


def test_herd_numbers_follow_from_the_arithmetic():
    import herd_10x as h

    assert pytest.approx(1666.7, abs=0.1) == h.PROCESSES * h.ITEMS / h.TTL
    assert pytest.approx(166.7, abs=0.1) == h.ITEMS / h.TTL
    got = expected("herd_10x")
    assert re.search(r"fixed TTL .* 50,000 \(at 30 s\)", got)

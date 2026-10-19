"""Part 6: every program on the page prints the output the page shows (out/<name>.txt)."""

import subprocess

import pytest
from test_programs5 import HERE, LINUX, PY314, expected, interpreter, numbers, run, shape

EXACT = [
    "work_in_work_out",
    "queue_basics",
    "queue_order",
    "shutdown_demo",
    "sentinel_legacy",
    "worker_hang",
    "seller_line",
]
TIMED = ["workers", "gateway_v7"]  # times within 60 ms
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
        if w in (1199,):  # a price, not a time
            assert g == w
        else:
            assert abs(g - w) <= TOLERANCE_MS, (name, g, w)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_gateway_v7_counts_are_exact():
    got = run("gateway_v7")
    for line in (
        "10 answered {'seller-b 1199': 10}",
        "20 told 'busy'",
        "refused at the door: 20; seller calls not made: {'seller-c: line full': 5, "
        "'seller-d: over its rate': 5, 'seller-e: line full': 6}",
        "at 300 ms: 10 requests in progress, 8 rows in the audit queue",
        "10 told 'busy'",
        "audit rows written: 20 | background failures: none",
    ):
        assert line in got, line


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_backpressure_counts():
    got = run("backpressure")
    assert shape(got) == shape(expected("backpressure"))
    unbounded, bounded = got.splitlines()
    made, written, waiting, put_ms = numbers(unbounded.split(":", 1)[1])[1:]
    assert (made, written, waiting, put_ms) == (30, 9, 20, 0)
    made, written, waiting, put_ms = numbers(bounded.split(":", 1)[1])[1:]
    assert made == 13 and written == 9 and waiting == 3 and 20 <= put_ms <= 30


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_rate_demo_allows_the_burst_then_the_rate():
    got = run("rate_demo")
    pattern = got.splitlines()[1]
    assert pattern.startswith("xxxxxxx.")
    assert 23 <= pattern.count("x") <= 25


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_standing_queue_counts():
    got = run("standing_queue")
    assert shape(got) == shape(expected("standing_queue"))
    lines = got.splitlines()
    on_time, late, stale, busy = numbers(lines[0].split(";", 1)[1])
    depth, wait = numbers(lines[1])
    assert 55 <= on_time <= 65 and late == 300 - on_time and stale == 0 and busy == 0
    assert 95 <= depth <= 110 and 950 <= wait <= 1100
    on_time, late, stale, busy = numbers(lines[2].split(";", 1)[1])
    depth, wait = numbers(lines[3])
    assert 190 <= on_time <= 215 and late == 0 and on_time + stale + busy == 300 and wait <= 200


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_request_cost_is_about_7_kb():
    got = run("request_cost")
    assert shape(got) == shape(expected("request_cost"))
    kb = numbers(got.splitlines()[1])[0]
    assert 5 <= kb <= 9  # work_in_work_out.py uses 7


def test_work_in_work_out_uses_the_measured_figure():
    import work_in_work_out

    assert work_in_work_out.KB_PER_REQUEST == 7
    assert work_in_work_out.ARRIVALS - work_in_work_out.CAPACITY == 1_000


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13", "3.14"])
def test_queue_basics_sentinels_and_the_hang_are_the_same_on_every_version(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    for name in ("queue_basics", "sentinel_legacy", "worker_hang", "queue_order"):
        assert run(name, python) == expected(name), (version, name)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12"])
def test_shutdown_does_not_exist_before_3_13(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    result = subprocess.run([python, "shutdown_demo.py"], cwd=HERE, capture_output=True, text=True)
    assert result.returncode != 0
    assert "AttributeError: 'Queue' object has no attribute 'shutdown'" in result.stderr


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_shutdown_demo_on_3_13():
    python = interpreter("3.13")
    if python is None:
        pytest.skip("Python 3.13 is not installed here")
    assert run("shutdown_demo", python) == expected("shutdown_demo")

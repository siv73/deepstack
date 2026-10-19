"""Part 3: every program on the page prints the output the page shows (out/<name>.txt)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
LINUX = sys.platform.startswith("linux")

EXACT = ["coro_vs_task", "except_star", "eager"]  # no clock involved
TIMED = [
    "two_awaits",
    "gather_demo",
    "taskgroup_demo",
    "as_completed_demo",
    "semaphore_demo",
    "timeouts_demo",
    "gateway_v4",
    "gather_vs_taskgroup",
    "wait_demo",
]
TOLERANCE_MS = 60


def run(name):
    result = subprocess.run(
        [sys.executable, "-W", "default", f"{name}.py"],
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert result.stderr == "", result.stderr  # no stray warnings or tracebacks
    return result.stdout


def expected(name):
    return (HERE / "out" / f"{name}.txt").read_text()


def numbers(text):
    return [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)]


def shape(text):
    return re.sub(r"\d[\d,]*", "N", text)


@pytest.mark.parametrize("name", EXACT)
def test_exact_output(name):
    assert run(name) == expected(name)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("name", TIMED)
def test_timed_output_matches_within_tolerance(name):
    got, want = run(name), expected(name)
    assert shape(got) == shape(want)
    for g, w in zip(numbers(got), numbers(want), strict=True):
        assert abs(g - w) <= TOLERANCE_MS, (name, g, w)


@pytest.mark.skipif(not LINUX, reason="EMFILE and open-file limits as on Linux")
def test_burst_output():
    got = run("burst").splitlines()
    assert got[1] == "answered 0 of 500; TaskGroup failed, error codes: ['EMFILE']"
    m = re.fullmatch(r"answered 500 of 500 in about ([\d,]+) ms; most open at once: 50", got[3])
    assert m and 800 <= int(m[1].replace(",", "")) <= 1100
    assert shape(run("burst")) == shape(expected("burst"))


@pytest.mark.skipif(not LINUX, reason="timings recorded on Linux")
def test_pool_wait_output():
    got = run("pool_wait")
    assert shape(got) == shape(expected("pool_wait"))
    lines = got.splitlines()
    m = re.fullmatch(r"slowest request ([\d,]+) ms; over budget: 18 of 20; no offer: 0 of 20", lines[1])
    assert m and abs(int(m[1].replace(",", "")) - 1770) <= TOLERANCE_MS
    assert re.fullmatch(r"slowest request 2[45]0 ms; over budget: 0 of 20; no offer: 16 of 20", lines[3])


@pytest.mark.skipif(not LINUX, reason="timings recorded on Linux")
def test_overload_output():
    got = run("overload").splitlines()
    assert got[1] == "burst 1 answered 10 of 50; burst 2 answered 0 of 50"
    assert got[2] == "seller jobs done: 100; useful: 10; seller busy until about 1,500 ms"
    assert got[4] == "burst 1 answered 10 of 50; burst 2 answered 10 of 50"
    assert got[5] == "seller jobs done: 40; useful: 20; seller busy until about 700 ms"


@pytest.mark.skipif(not LINUX, reason="timings recorded on Linux")
def test_fan_out_500_output():
    got = run("fan_out_500").splitlines()
    m = re.fullmatch(
        r"answered 500, timed out 0, failed 0 of 500 in about ([\d,]+) ms; most in flight: 50", got[1]
    )
    assert m and int(m[1].replace(",", "")) < 1000
    assert got[3] == "answered 250, timed out 250, failed 0 of 500 in about 1,000 ms; most in flight: 50"

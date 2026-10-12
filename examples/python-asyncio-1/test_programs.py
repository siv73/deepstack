"""Every program on the page prints exactly the output the page shows (out/<name>.txt)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent

# Programs on the toy loop or with no clock print the same text on every run.
EXACT = [
    "gen_basics",
    "gen_send",
    "gen_throw",
    "gen_close",
    "gen_yield_from",
    "loop_step1",
    "loop_step2",
    "coro_basics",
    "never_awaited",
    "await_chain",
    "toyloop_demo",
    "gateway_v1",
    "fault",
    "real_io",
    "forgot_await",
]
# Programs that really sleep (or really block) print times that can drift by a few ms.
TIMED = ["gateway_v0", "gateway_threads", "blocking"]


def run(name):
    result = subprocess.run(
        [sys.executable, "-W", "default", f"{name}.py"],
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert result.stderr == "", result.stderr  # no stray warnings or tracebacks
    return result.stdout


def expected(name):
    return (HERE / "out" / f"{name}.txt").read_text()


@pytest.mark.parametrize("name", EXACT)
def test_exact_output(name):
    assert run(name) == expected(name)


def numbers(text):
    return [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)]


@pytest.mark.parametrize("name", TIMED)
def test_timed_output_matches_within_tolerance(name):
    got, want = run(name), expected(name)
    # Same words in the same order; every number within 30 ms of what the page shows.
    assert re.sub(r"\d[\d,]*", "N", got) == re.sub(r"\d[\d,]*", "N", want)
    for g, w in zip(numbers(got), numbers(want), strict=True):
        assert abs(g - w) <= 30, (g, w)

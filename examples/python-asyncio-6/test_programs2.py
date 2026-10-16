"""Part 2: every program on the page prints the output the page shows (out/<name>.txt)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
LINUX = sys.platform.startswith("linux")

# No clock involved, or a clock that cannot drift past a 10 ms rounding step.
EXACT = ["loop_iteration", "future_basics", "future_await", "unregister_bug", "gateway_proto", "read_trace"]
LINUX_EXACT = ["select_limit", "fd_limit"]  # epoll and fd numbering as on Linux
# Programs on real sockets and real clocks: times can drift by a few ms from run to run.
TIMED = [
    "blocking_socket",
    "nonblock",
    "select_five",
    "callbacks",
    "nap",
    "task_steps",
    "run_lifecycle",
    "gateway_v2",
    "gateway_v3",
    "fault_v3",
    "busy_loop",
    "poll_vs_future",
    "cross_thread",
    "lag_probe",
]
TOLERANCE_MS = 60


def run(name):
    result = subprocess.run(
        [sys.executable, "-W", "default", f"{name}.py"],
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert result.stderr == "", result.stderr  # no stray warnings or tracebacks
    return result.stdout


def expected(name):
    return (HERE / "out" / f"{name}.txt").read_text()


@pytest.mark.parametrize("name", EXACT)
def test_exact_output(name):
    assert run(name) == expected(name)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("name", LINUX_EXACT)
def test_exact_output_on_linux(name):
    assert run(name) == expected(name)


def numbers(text):
    return [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)]


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux (selector names, errno names)")
@pytest.mark.parametrize("name", TIMED)
def test_timed_output_matches_within_tolerance(name):
    got, want = run(name), expected(name)
    # Same words in the same order; every number within 60 ms of what the page shows.
    assert re.sub(r"\d[\d,]*", "N", got) == re.sub(r"\d[\d,]*", "N", want)
    for g, w in zip(numbers(got), numbers(want), strict=True):
        assert abs(g - w) <= TOLERANCE_MS, (name, g, w)

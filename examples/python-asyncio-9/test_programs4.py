"""Part 4: every program on the page prints the output the page shows (out/<name>.txt)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
LINUX = sys.platform.startswith("linux")

EXACT = ["trap3_vanish", "trap3_silent", "debug_demo"]  # no timed numbers in the output
TIMED = [
    "trap1_forgotten_await",
    "trap2_blocking_io",
    "trap2_shared_pool",
    "trap4_gather",
    "trap5_swallow",
    "trap6_silent_timeouts",
    "gateway_v5",
]
TOLERANCE_MS = 60


def run(name, *flags):
    result = subprocess.run(
        [sys.executable, "-W", "default", *flags, f"{name}.py"],
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


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
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


def cpu_rows(text):
    pattern = (
        r"(.+?)\s*: 6 scorings in about ([\d,]+) ms; worst timer lag ([\d,]+) ms; best seller-b at 1,199"
    )
    rows = {}
    for line in text.splitlines():
        m = re.fullmatch(pattern, line)
        assert m, line
        rows[m[1]] = (int(m[2].replace(",", "")), int(m[3].replace(",", "")))
    return rows


def test_cpu_program_shape_and_the_page_run():
    assert shape(run("trap2_cpu")) == shape(expected("trap2_cpu"))
    cpu_rows(expected("trap2_cpu"))


def cpu_relationships_hold(rows):
    loop_ms, loop_lag = rows["on the loop"]
    threads_ms, threads_lag = rows["2 threads"]
    procs_ms, procs_lag = rows["2 processes"]
    return [
        loop_lag >= 0.7 * loop_ms,  # the loop was frozen for nearly all of it
        threads_ms >= 0.8 * loop_ms,  # one GIL: no faster than on the loop
        threads_lag < 0.5 * loop_lag,  # but the loop gets turns between switches
        procs_ms < 0.85 * threads_ms,  # two cores really work at once
        procs_lag <= 30,  # and the loop stays free
    ]


def test_cpu_work_blocks_the_loop_threads_do_not_speed_it_up_processes_do():
    # Timings on a shared CI runner are noisy: the relationships must hold in one of three runs.
    results = []
    for _ in range(3):
        results.append(cpu_relationships_hold(cpu_rows(run("trap2_cpu"))))
        if all(results[-1]):
            break
    assert all(results[-1]), results

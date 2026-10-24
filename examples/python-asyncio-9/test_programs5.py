"""Part 5: every program on the page prints the output the page shows (out/<name>.txt)."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
LINUX = sys.platform.startswith("linux")
PY314 = sys.version_info[:2] == (3, 14)

EXACT = [
    "cancel_request",
    "where_cancel_lands",
    "bookkeeping",
    "refuse_cancel",
    "stale_cancel",
    "audit_shield",
    "shield_limits",
]
TIMED = ["cancel_trace", "cleanup", "slow_cleanup", "thread_deadline", "hangup_cost", "gateway_v6"]
TOLERANCE_MS = 60


def run(name, python=sys.executable):
    result = subprocess.run(
        [python, "-W", "default", f"{name}.py"],
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
        assert abs(g - w) <= TOLERANCE_MS, (name, g, w)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_hangup_load_counts():
    got = run("hangup_load")
    assert shape(got) == shape(expected("hangup_load"))
    (v5_waiting, v5_threads), (v6_waiting, v6_threads) = [
        (int(a), int(b)) for a, b in re.findall(r"in progress: (\d+)\n.*?still busy: (\d+)", got, flags=re.S)
    ]
    assert v5_waiting >= 40 and v5_threads == 4  # gateway v5 keeps working for 10 shoppers who left
    assert v6_waiting == 0 and v6_threads == 0  # gateway v6 stops it all


def interpreter(version):
    uv = shutil.which("uv")
    if not uv:
        return None
    found = subprocess.run([uv, "python", "find", "--no-project", version], capture_output=True, text=True)
    return found.stdout.strip() if found.returncode == 0 else None


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13", "3.14"])
def test_version_probe_on_each_installed_version(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    got, want = run("version_probe", python).splitlines(), expected(f"version_probe_{version}").splitlines()
    assert got[:3] + got[4:] == want[:3] + want[4:]
    # Line 3: the "exception in shielded future" report exists in 3.14.0 to 3.14.8 only.
    older = expected("version_probe_3.13").splitlines()[3]  # the same line on 3.11 to 3.13
    assert got[3] in (want[3], older)


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13"])
def test_bookkeeping_is_the_same_on_older_versions(version):
    """The page says cases 1 and 2 (and 3) print the same lines on 3.11 to 3.14."""
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    assert run("bookkeeping", python) == expected("bookkeeping")


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12"])
def test_stale_cancel_is_harmless_before_3_13(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    first = run("stale_cancel", python).splitlines()[0]
    assert first.endswith("the shopper gets: 502 bad price data from a seller; audit rows: 1")

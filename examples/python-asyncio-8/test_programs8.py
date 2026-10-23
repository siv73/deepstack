"""Part 8: every program on the page prints the output the page shows (out/<name>.txt)."""

import re

import pytest
from test_programs5 import LINUX, PY314, expected, interpreter, numbers, run, shape

EXACT = ["runner_sigint", "exit_stack", "wrong_loop", "signals_threads", "stop_ways"]
TIMED = ["signal_handlers", "asyncgen_late", "deploy_v8", "deploy_v9", "drain_deadline", "cleanup_order"]
TOLERANCE_MS = 60
COUNTS = {0, 1, 2, 3, 4, 5, 8, 9, 10, 15, 20, 25, 29, 1199, 1200}  # counts, codes and prices, not times


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
        if w in COUNTS:
            assert g == w, (name, g, w)
        else:
            assert abs(g - w) <= TOLERANCE_MS, (name, g, w)


@pytest.mark.skipif(not (LINUX and PY314), reason="output recorded on Linux with Python 3.14")
def test_hangs_are_killed_and_fixes_exit():
    got = run("hang_forever")
    assert shape(got) == shape(expected("hang_forever"))
    outcomes = re.findall(r"^(.*?): (SIGKILL|exit 0) after about (\d+) ms", got, flags=re.M)
    assert [o for _, o, _ in outcomes] == ["SIGKILL", "exit 0"] * 3
    for case, outcome, ms in outcomes:
        if outcome == "exit 0":
            assert int(ms) <= 700, case  # the fixed versions stop at once, far inside the grace period


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_lb_race_refusals_only_without_a_pause():
    got = run("lb_race")
    assert shape(got) == shape(expected("lb_race"))
    without, with_pause = got.splitlines()
    refused = int(re.search(r"'refused': (\d+)", without).group(1))
    assert 10 <= refused <= 17  # about half of 300 ms of requests at one every 10 ms
    assert "refused" not in with_pause


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13", "3.14"])
def test_version_probe8_on_each_installed_version(version):
    python = interpreter(version)
    if python is None:
        pytest.skip(f"Python {version} is not installed here")
    assert run("version_probe8", python) == expected(f"version_probe8_{version}")


@pytest.mark.skipif(not LINUX, reason="output recorded on Linux")
def test_deploy_counts_are_exact():
    v8, v9 = run("deploy_v8"), run("deploy_v9")
    assert "20 shoppers: {'no answer (connection closed)': 20}" in v8
    assert "return code -15" in v8
    assert "20 shoppers: {'seller-b 1199': 20}" in v9
    assert "5 quick quotes: {'seller-b 1199': 5}" in v9
    assert "a shopper arriving at 150 ms: refused (ConnectionRefusedError)" in v9
    assert "fills: 1 finished, 0 cancelled" in v9
    assert "feed thread stopped: alive = False" in v9
    assert "audit rows: 29, lost: 0" in v9
    assert "return code 0; stderr lines: 0" in v9

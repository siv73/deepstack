"""SIGTERM behaviour, run in a real child process (Unix only)."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="add_signal_handler is Unix-only"),
    pytest.mark.skipif(sys.version_info < (3, 13), reason="Queue.shutdown needs Python 3.13+"),
]
SCRIPT = Path(__file__).with_name("graceful.py")


def _run(*args: str) -> subprocess.CompletedProcess:
    p = subprocess.Popen([sys.executable, str(SCRIPT), *args], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "ready"
    time.sleep(0.1)  # two jobs are now in flight
    p.send_signal(signal.SIGTERM)
    out, _ = p.communicate(timeout=10)
    return subprocess.CompletedProcess(p.args, p.returncode, out)


def test_sigterm_with_handler_finishes_in_flight_jobs_and_exits_zero():
    r = _run()
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert sorted(lines[:2]) == ["finished job 0", "finished job 1"]
    assert lines[-1] == "exited cleanly"
    assert "finished job 2" not in r.stdout  # queued jobs were not started


def test_sigterm_without_handler_kills_mid_job():
    r = _run("--no-handler")
    assert r.returncode == -signal.SIGTERM
    assert r.stdout == ""  # no job finished, no finally/cleanup ran

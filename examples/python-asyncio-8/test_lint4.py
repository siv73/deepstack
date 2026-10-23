"""Part 4: what ruff's asyncio rules catch in lint_cases.py, and what they miss."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
RULES = "ASYNC,RUF006,BLE001"


def lint():
    ruff = shutil.which("ruff") or str(Path(sys.executable).with_name("ruff"))
    result = subprocess.run(
        [
            ruff,
            "check",
            "--no-cache",
            "--isolated",
            "--select",
            RULES,
            "--output-format",
            "concise",
            "lint_cases.py",
        ],
        cwd=HERE,
        capture_output=True,
        text=True,
    )
    return result.stdout


def flagged_functions(output):
    source = (HERE / "lint_cases.py").read_text().splitlines()
    names = []
    for line in output.splitlines():
        if line.startswith("lint_cases.py:"):
            row = int(line.split(":")[1])
            defs = [s for s in source[:row] if s.startswith("async def ")]
            names.append((defs[-1].split()[2].split("(")[0], line.split()[1]))
    return names


def test_the_page_shows_ruffs_real_output():
    assert lint() == (HERE / "out" / "lint_cases.txt").read_text()


def test_ruff_catches_four_of_the_seven():
    assert flagged_functions(lint()) == [
        ("sleeps", "ASYNC251"),
        ("fetches", "ASYNC210"),
        ("fires_and_forgets", "RUF006"),
        ("swallows", "BLE001"),
    ]


@pytest.mark.parametrize("missed", ["calls_the_sdk", "swallows_and_logs", "forgets_the_await"])
def test_and_misses_three(missed):
    assert missed not in [name for name, _ in flagged_functions(lint())]

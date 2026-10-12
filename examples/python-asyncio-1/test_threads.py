"""The measured thread cost shown on the page, and a fresh measurement's shape."""

import json
import platform
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def test_measured_file_is_complete():
    m = json.loads((HERE / "measured.json").read_text())
    assert m["python"].startswith("3.14")
    assert m["stack_size_setting"] == 0  # Python left the stack size to the platform
    assert m["virtual_kib_per_thread"] > m["resident_kib_per_thread"] * 100


@pytest.mark.skipif(platform.system() != "Linux", reason="reads /proc/self/status")
def test_a_waiting_thread_reserves_far_more_than_it_uses():
    from thread_cost import measure

    m = measure(200)
    assert m["virtual_kib_per_thread"] >= 1024  # at least 1 MiB reserved per thread
    assert m["resident_kib_per_thread"] < 512  # but only a little actually touched

"""Measure what an idle, waiting thread costs on this machine (Linux only).

Run with --save to record a measurement in measured.json (the page shows that file).
"""

import json
import platform
import resource
import sys
import threading
import time
from pathlib import Path


def memory_kib():
    """Resident (actually used) and virtual (reserved) memory of this process, in KiB."""
    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        fields[key] = value
    return int(fields["VmRSS"].split()[0]), int(fields["VmSize"].split()[0])


def measure(n=500):
    stop = threading.Event()
    rss_before, virt_before = memory_kib()
    start = time.perf_counter()
    threads = [threading.Thread(target=stop.wait) for _ in range(n)]
    for t in threads:
        t.start()
    start_us = (time.perf_counter() - start) / n * 1e6
    rss_after, virt_after = memory_kib()
    stop.set()
    for t in threads:
        t.join()
    soft_stack_limit = resource.getrlimit(resource.RLIMIT_STACK)[0]
    return {
        "threads": n,
        "python": platform.python_version(),
        "system": f"{platform.system()} {platform.machine()}",
        "stack_size_setting": threading.stack_size(),
        "stack_limit_kib": soft_stack_limit // 1024,
        "start_us_per_thread": round(start_us),
        "virtual_kib_per_thread": round((virt_after - virt_before) / n),
        "resident_kib_per_thread": round((rss_after - rss_before) / n),
    }


if __name__ == "__main__":
    result = measure()
    for key, value in result.items():
        print(f"{key}: {value}")
    if "--save" in sys.argv:
        Path(__file__).with_name("measured.json").write_text(json.dumps(result, indent=1) + "\n")

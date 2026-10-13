"""Measure: what one select() call costs when many registered sockets are idle.

Run it to refresh measured_idle.json; the page shows the numbers from that file.
"""

import json
import platform
import selectors
import socket
import sys
import time
from pathlib import Path

CALLS = 2000


def cost_us(selector_cls, idle):
    pairs = [socket.socketpair() for _ in range(idle)]
    with selector_cls() as sel:
        for a, _b in pairs:
            sel.register(a, selectors.EVENT_READ)  # nobody ever writes: always idle
        start = time.perf_counter()
        for _ in range(CALLS):
            sel.select(timeout=0)
        took = (time.perf_counter() - start) / CALLS
    for a, b in pairs:
        a.close()
        b.close()
    return round(took * 1e6, 1)


rows = []
for idle in (10, 100, 500):
    rows.append(
        {
            "idle": idle,
            "select_us": cost_us(selectors.SelectSelector, idle),
            "epoll_us": cost_us(selectors.EpollSelector, idle),
        }
    )
rows.append({"idle": 5000, "select_us": None, "epoll_us": cost_us(selectors.EpollSelector, 5000)})
result = {
    "python": platform.python_version(),
    "system": f"{platform.system()} {platform.machine()}",
    "calls_per_point": CALLS,
    "rows": rows,
}
Path(__file__).with_name("measured_idle.json").write_text(json.dumps(result, indent=1) + "\n")
json.dump(result, sys.stdout, indent=1)

"""Rung 3: the same incident on gateway v10. What do its metrics, logs and task names show?"""

import asyncio
import re

import gateway_v10
import incident
from observe import json_lines

lines = json_lines("gateway")


async def look(gateway):
    loop = asyncio.get_running_loop()
    lines.filters[0].start = loop.time() - 1.0  # at_ms counts from the moment the store stopped
    requests = sorted(t.get_name() for t in asyncio.all_tasks() if t in gateway.requests)
    one = next(t for t in gateway.requests if t.get_name() == "shop-6 kettle-1l")
    graph = asyncio.format_call_graph(one, limit=-3) if hasattr(asyncio, "format_call_graph") else ""
    return [
        f"request Tasks by name: {requests}",
        "format_call_graph(one of them, limit=-3):",
        re.sub(r"File '/[^']*/([^'/]+)'", r"File '\1'", re.sub(r"id=0x[0-9a-f]+", "id=0x…", graph)),
    ]


def show(event):
    keep = ("at_ms", "level", "event", "request_id", "best", "ms", "waited_ms")
    return {k: event[k] for k in keep if k in event}


if __name__ == "__main__":
    report, seen, gateway = incident.main(look, cls=gateway_v10.Gateway, patience=2.0)
    print("\n".join(seen))
    print(report[1])
    print("JSON log lines for shop-6, from the moment the store stopped:")
    for event in lines.events():
        if event["request_id"] == "shop-6" and event["at_ms"] is not None and event["at_ms"] >= 0:
            print(f"  {show(event)}")
    snap = gateway.snapshot()
    print(f"audit timeouts: {snap['audit timeouts']}; requests: {snap['requests']}")
    print(f"request ms, histogram p50/p99 (upper bounds): {snap['request ms p50/p99']}")

"""Rung 2 (Python 3.14+): the whole await chain of one stuck request, and of one audit writer."""

import asyncio
import re

import incident


def tidy(text):
    """Make the graph the same on every machine: file names only, no ids, no stdlib line numbers."""
    text = re.sub(r"id=0x[0-9a-f]+", "id=0x…", text)
    text = re.sub(r"Task-\d+", "Task-N", text)
    text = re.sub(r"File '[^']*/(asyncio/[^']+)', line \d+", r"File '\1'", text)  # stdlib: release-dependent
    return re.sub(r"File '/[^']*/([^'/]+)'", r"File '\1'", text)


async def look(gateway):
    tasks = asyncio.all_tasks()
    request = next(t for t in tasks if t.get_coro().__qualname__ == "Gateway.serve")
    writer = next(t for t in tasks if t.get_name() == "audit-writer")
    writes = [t for t in tasks if t.get_name() == "audit"]
    return [
        "-- asyncio.format_call_graph(one stuck request Task) --",
        tidy(asyncio.format_call_graph(request)),
        "-- asyncio.format_call_graph(one audit-writer Task) --",
        tidy(asyncio.format_call_graph(writer)),
        f"-- asyncio.format_call_graph(one of the {len(writes)} 'audit' Tasks) --",
        tidy(asyncio.format_call_graph(writes[0])),
    ]


if __name__ == "__main__":
    report, seen, _ = incident.main(look)
    print("\n".join(seen))

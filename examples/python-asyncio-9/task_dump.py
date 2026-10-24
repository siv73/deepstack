"""Rung 2: from inside the process, list every Task and where it is waiting: all_tasks() and get_stack()."""

import asyncio
import re
from collections import Counter
from pathlib import Path

import incident


def where(frame):
    """'gateway_v9.py:96 in serve' for our files; stdlib files get no line number (it changes per release)."""
    path = Path(frame.f_code.co_filename)
    if "asyncio" in path.parts or "python3" in str(path):
        return f"asyncio/{path.name} in {frame.f_code.co_name}"
    return f"{path.name}:{frame.f_lineno} in {frame.f_code.co_name}"


async def look(gateway):
    me = asyncio.current_task()
    tasks = [t for t in asyncio.all_tasks() if t is not me and not t.get_name().startswith("shopper")]
    lines = [f"asyncio.all_tasks(): {len(tasks)} Tasks of the gateway (the program's own left out)"]
    kinds = Counter()
    for task in tasks:
        stack = task.get_stack()  # one frame for a suspended coroutine: the Task's own one
        coro = task.get_coro().__qualname__
        name = re.sub(r"Task-\d+", "Task-N", task.get_name())
        kinds[f"{name:<14} {coro:<22} frames: {len(stack)}  {where(stack[-1])}"] += 1
    for row, n in sorted(kinds.items()):
        lines.append(f"  {n} x {row}")
    return lines


if __name__ == "__main__":
    report, seen, _ = incident.main(look)
    print("\n".join(seen))

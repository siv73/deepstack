"""Rung 2 (Python 3.14+): the same incident seen from outside: python -m asyncio ps and pstree.

The program inspects itself from a child process, as an operator would from a shell. On Linux
with Yama ptrace restrictions (GitHub's runners, many distributions), a process may read another
only if allowed; prctl(PR_SET_PTRACER, ANY) below is what `setpriv --ptracer any` sets.
"""

import asyncio
import ctypes
import os
import re
import sys

import incident

PR_SET_PTRACER, PR_SET_PTRACER_ANY = 0x59616D61, ctypes.c_ulong(-1)


def allow_inspection():
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0)  # fails harmlessly without Yama


def tidy(text):
    """The same on every machine: no ids, no paths, no stdlib line numbers, numbered names as Task-N."""
    text = re.sub(r"0x[0-9a-f]+", "0x…", text)
    text = re.sub(r"Task-\d+", "Task-N", text)
    text = re.sub(r" /\S*/asyncio/(\S+?):\d+", r" asyncio/\1", text)  # stdlib frames
    return re.sub(r" /\S*/(\S+?:\d+)", r" \1", text)  # our frames: file name and line


def chains(rest):
    """Split the text after 'tid task-id name' into its 'a -> b -> c' chains and single words."""
    words, groups = rest.split(), []
    for word in words:
        if groups and (word == "->" or groups[-1][-1] == "->"):
            groups[-1].append(word)
        else:
            groups.append([word])
    return [" ".join(g) for g in groups]


def ps_rows(text):
    """Each ps row as (task name, coroutine stack, awaiter name). Columns overflow, so parse, not slice."""
    rows = []
    for line in text.splitlines()[2:]:
        _tid, _task_id, name, rest = line.split(maxsplit=3)
        parts = chains(rest)
        stack = parts[0]
        awaiter = parts[2] if len(parts) == 4 else "-"  # stack, [awaiter chain, awaiter name,] awaiter id
        rows.append((name, stack, awaiter))
    return rows


async def tool(command):
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "asyncio", command, str(os.getpid()),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )  # fmt: skip
    out, _ = await proc.communicate()
    return tidy(out.decode())


async def look(gateway):
    ps = await tool("ps")
    tree = await tool("pstree")
    header = re.split(r" {2,}", ps.splitlines()[0].strip())
    rows = [r for r in ps_rows(ps) if r[1].endswith("Gateway.serve") or "audit" in r[0]]
    blocks = re.split(r"^(?=└── \(T\))", tree, flags=re.M)
    stuck = next(b for b in blocks if "Gateway._audit" in b)
    lines = [
        f"$ python -m asyncio ps PID   -> {len(ps.splitlines()) - 2} rows, header: {' | '.join(header)}",
        "the gateway's rows, as task name | coroutine stack | awaiter name:",
    ]
    counted = {}
    for row in rows:
        counted[row] = counted.get(row, 0) + 1
    lines += [
        f"  {n} x {name} | {stack} | {awaiter}" for (name, stack, awaiter), n in sorted(counted.items())
    ]
    lines += ["$ python -m asyncio pstree PID   -> the first stuck request's branch:", stuck.rstrip()]
    return lines


if __name__ == "__main__":
    allow_inspection()
    report, seen, _ = incident.main(look)
    print("\n".join(seen))

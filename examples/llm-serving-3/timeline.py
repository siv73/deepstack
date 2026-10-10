"""The six-request toy behind the page's step-through timeline, counted in steps instead of seconds.

Steps are numbered from 0 here; the page labels them from 1.

A request's prefill takes one step and produces its first token; each later token takes one
decode step. Cells: "P" prefill, "d" decode, "pad" a finished row still in a static batch,
"wait" an empty slot while the GPU waits for a full batch, "" an empty slot.
"""

# id, step it arrives in, tokens to generate
REQUESTS = [("A", 0, 2), ("B", 0, 6), ("C", 1, 3), ("D", 2, 2), ("E", 3, 4), ("F", 4, 3)]


def static(reqs=REQUESTS, slots=3) -> list[list[str]]:
    cols, t = [], 0
    for i in range(0, len(reqs), slots):
        batch = reqs[i : i + slots]
        while t < max(arr for _, arr, _ in batch):  # wait until the batch is full
            cols.append(["wait"] * slots)
            t += 1
        for k in range(max(n for *_, n in batch)):  # run until the longest request is done
            cols.append([("P" if k == 0 else "d" if k < n else "pad") + ":" + r for r, _, n in batch])
            t += 1
    return cols


def continuous(reqs=REQUESTS, slots=3) -> list[list[str]]:
    cols, t, waiting, row = [], 0, [], [None] * slots  # row[i] = [id, tokens made, tokens wanted]
    todo = list(reqs)
    while todo or waiting or any(row):
        waiting += [r for r in todo if r[1] == t]
        todo = [r for r in todo if r[1] != t]
        col = ["d:" + s[0] if s else "" for s in row]
        for i in range(slots):  # free slots take waiting requests, first come first served
            if row[i] is None and waiting:
                r, _, n = waiting.pop(0)
                row[i], col[i] = [r, 0, n], "P:" + r
        for i, s in enumerate(row):
            if s:
                s[1] += 1
                if s[1] == s[2]:
                    row[i] = None  # finished: the slot is free for the next step
        cols.append(col)
        t += 1
    return cols


def count(cols: list[list[str]], kind: str) -> int:
    return sum(c.split(":")[0] == kind for col in cols for c in col)


def finish_step(cols: list[list[str]], rid: str) -> int:
    """Last step in which request `rid` made a token (static rows keep running as padding)."""
    return max(i for i, col in enumerate(cols) for c in col if c in ("P:" + rid, "d:" + rid))

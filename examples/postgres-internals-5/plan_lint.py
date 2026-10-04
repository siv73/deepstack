"""Read EXPLAIN ANALYZE text output and point at the usual suspects."""

import re

NODE = re.compile(
    r"^(?P<indent>\s*)(?:->\s+)?(?P<name>[A-Z][\w ]+?)(?: (?:on|using) .*?)?\s+"
    r"\(cost=[\d.]+\.\.[\d.]+ rows=(?P<est>\d+) width=\d+\)\s+"
    r"\(actual (?:time=[\d.]+\.\.[\d.]+ )?rows=(?P<rows>[\d.]+) loops=(?P<loops>\d+)\)"
)


def lint(plan_text: str, ratio: float = 10.0) -> list[str]:
    findings, node = [], "?"
    for line in plan_text.splitlines():
        m = NODE.match(line)
        if m:
            node = m["name"].strip()
            loops = int(m["loops"])
            est, actual = int(m["est"]) * loops, float(m["rows"]) * loops  # both are per loop
            if max(est, actual) >= ratio * max(min(est, actual), 1):
                findings.append(f"{node}: estimated {est:g} rows, got {actual:g}")
            continue
        if "external merge" in line:
            findings.append(f"{node}: sort spilled to disk")
        b = re.search(r"Batches: (\d+)", line)
        if b and int(b[1]) > 1:
            findings.append(f"{node}: hash used {b[1]} batches (spilled to disk)")
        if re.search(r"lossy=\d+", line):
            findings.append(f"{node}: bitmap went lossy, every row on those pages rechecked")
    return findings

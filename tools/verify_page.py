#!/usr/bin/env python3
"""Static verification of a built teach-site topic page.

Usage (from the project root): uv run tools/verify_page.py <slug> [--strict]
Checks site/<slug>/index.html. Exit 0 = no errors (warnings may remain), 1 = errors.
--strict turns warnings into errors. Fix every error before delivering the page;
resolve every warning or accept it consciously.
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

errors, warns = [], []


def E(msg):
    errors.append(msg)


def W(msg):
    warns.append(msg)


RISKY = re.compile(
    r"\bRFC\s?\d{3,5}\b|\b\d+\.\d+(\.\d+)?\b|\bMUST\b|\bSHOULD\b|\bREQUIRED\b|\b(?i:deprecat\w*|defaults?|removed)\b"
    r"|\b(19|20)\d\d\b|\d+\s?%|\b\d+\s?(?i:ms|seconds?|minutes?|hours?|days?|KB|MB|GB|bytes?|bits?|characters?)\b"
)


def main(path, strict):
    p = Path(path)
    soup = BeautifulSoup(p.read_text(), "lxml")

    def js(id_):
        s = soup.find("script", id=id_)
        if not s:
            E(f"missing <script id={id_}>")
            return {}
        try:
            return json.loads(s.string or "")
        except Exception as e:  # noqa
            E(f"{id_} is not valid JSON: {e}")
            return {}

    meta, ledger = js("ts-meta"), js("ts-ledger")
    for k in ("slug", "title", "tldr"):
        if not meta.get(k):
            E(f"ts-meta is missing '{k}'")

    # ---- sources ----
    sources = {}
    for s in ledger.get("sources", []):
        sid = s.get("id")
        if not sid:
            E(f"source without id: {s}")
            continue
        sources[sid] = s
        if not str(s.get("url", "")).startswith("https://"):
            E(f"source {sid}: url must be https")
        for k in ("title", "kind", "accessed"):
            if not s.get(k):
                E(f"source {sid}: missing '{k}'")
        if s.get("kind") not in ("primary", "secondary"):
            E(f"source {sid}: kind must be 'primary' or 'secondary'")

    # ---- claims ----
    claims = {}
    for c in ledger.get("claims", []):
        cid = c.get("id")
        if not cid:
            E(f"claim without id: {c}")
            continue
        claims[cid] = c
        if c.get("status") != "verified":
            E(f"claim {cid}: status is '{c.get('status')}'. Only verified claims stay; move others to 'cut'.")
        srcs = c.get("sources") or []
        if not srcs:
            E(f"claim {cid}: no sources")
        for sid in srcs:
            if sid not in sources:
                E(f"claim {cid}: unknown source {sid}")
        if not any(sources.get(sid, {}).get("kind") == "primary" for sid in srcs):
            E(f"claim {cid}: needs at least one primary (official) source")
        checks = c.get("checks") or []
        passes = {ch.get("pass") for ch in checks if ch.get("result") == "supported"}
        if not {1, 2} <= passes:
            E(f"claim {cid}: needs a 'supported' check in pass 1 (research) and pass 2 (fresh re-fetch)")
        if any(ch.get("result") in ("contradicted", "not_found") for ch in checks):
            E(f"claim {cid}: a check came back contradicted/not_found; fix or cut the claim")
        for ch in checks:
            if ch.get("source") and ch["source"] not in sources:
                E(f"claim {cid}: check cites unknown source {ch['source']}")
            if not ch.get("locator"):
                W(f"claim {cid}: check without a locator (section/heading)")

    # ---- page references ----
    used_claims = set()
    for node in soup.select(".ts-claim"):
        cid = node.get("data-claim")
        if not cid or cid not in claims:
            E(f"page marks claim '{cid}' that is not in the ledger: \"{node.get_text()[:80]}\"")
            continue
        used_claims.add(cid)
        ds = (node.get("data-src") or "").split()
        if not ds:
            E(f"claim {cid} in page has no data-src citation")
        for sid in ds:
            if sid not in claims[cid].get("sources", []):
                E(f"claim {cid} cites {sid} in the page but the ledger does not list it for that claim")
    for node in soup.select("[data-src]"):
        for sid in (node.get("data-src") or "").split():
            if sid not in sources:
                E(f"data-src references unknown source {sid}")
    for cid in claims:
        if cid not in used_claims and not any(
            cid in (n.get("data-claims") or "").split() for n in soup.select("[data-claims]")
        ):
            W(f"ledger claim {cid} is not used on the page")

    def check_claim_refs(node, what):
        if node.get("data-kind") == "reasoning":
            return
        refs = (node.get("data-claims") or "").split()
        if not refs:
            E(f'{what}: no data-claims (answer must trace to verified facts), not data-kind="reasoning"')
        for r in refs:
            if r not in claims:
                E(f"{what} references unknown claim {r}")
            used_claims.add(r)

    # ---- parts ----
    parts = soup.select("section.ts-part")
    if not parts:
        E("no parts")
    rungs, ids = [], set()
    for i, s in enumerate(parts, 1):
        tag = f"part {i}"
        pid = s.get("id")
        if not pid:
            E(f"{tag}: missing id")
        elif pid in ids:
            E(f"{tag}: duplicate id {pid}")
        ids.add(pid)
        try:
            rungs.append(int(s.get("data-rung", "")))
        except ValueError:
            E(f"{tag}: data-rung missing or not a number")
        if not s.get("data-min"):
            W(f"{tag}: no data-min estimate")
        if not s.find("h2"):
            E(f"{tag}: no <h2>")
        if not s.select(".ts-takeaway"):
            E(f"{tag}: no .ts-takeaway")
        if not s.select(".ts-quiz, .ts-order, .ts-predict, .ts-explain"):
            E(f"{tag}: no check (quiz/order/predict/explain)")
        # prose length
        clone = BeautifulSoup(str(s), "lxml")
        non_prose = ".ts-code, .ts-seq, .ts-graph, .ts-svg, .ts-quiz, .ts-order, .ts-predict, .ts-explain"
        for x in clone.select(non_prose + ", .ts-table-wrap, script"):
            x.decompose()
        words = len(clone.get_text(" ").split())
        if words > 450:
            W(f"{tag}: {words} words of prose (limit 450). Split the part.")
        # unmarked risky sentences
        for x in clone.select(".ts-claim, .ts-legacy .ts-claim"):
            x.decompose()
        for para in clone.select("p, li, td"):
            txt = para.get_text(" ").strip()
            for sent in re.split(r"(?<=[.!?])\s+", txt):
                if RISKY.search(sent) and len(sent) > 20:
                    W(f'{tag}: factual-looking sentence not marked as a claim: "{sent[:110]}"')
    if rungs != sorted(rungs):
        E(f"rungs out of order: {rungs}")
    missing = {1, 2, 3, 4, 5} - set(rungs)
    if missing:
        E(f"rungs missing: {sorted(missing)} (every topic climbs all five)")

    # ---- checks ----
    for i, q in enumerate(soup.select(".ts-quiz"), 1):
        what = f'quiz {i} ("{(q.select_one(".q") or q).get_text()[:50]}")'
        lis = q.select("ol > li")
        keys = [li.get("data-key") or chr(97 + j) for j, li in enumerate(lis)]
        if len(lis) < 3:
            E(f"{what}: fewer than 3 options")
        ans = q.get("data-answer")
        if ans not in keys:
            E(f"{what}: data-answer '{ans}' matches no option")
        for li, k in zip(lis, keys, strict=True):
            if k != ans and not li.get("data-why"):
                E(f"{what}: wrong option {k} has no data-why")
        if not q.select_one(".ts-why"):
            E(f"{what}: no .ts-why explanation")
        if not q.select_one(".q"):
            E(f"{what}: no .q question")
        check_claim_refs(q, what)
    for i, q in enumerate(soup.select(".ts-order"), 1):
        what = f"order {i}"
        if len(q.select("ol > li")) < 3:
            E(f"{what}: fewer than 3 items")
        check_claim_refs(q, what)
    for i, q in enumerate(soup.select(".ts-explain"), 1):
        pts = [x for x in (q.get("data-points") or "").split("|") if x.strip()]
        if len(pts) < 2:
            E(f"explain {i}: needs 2+ data-points")
        if not q.select_one(".ts-model"):
            E(f"explain {i}: no .ts-model")
        if not q.select_one(".q"):
            E(f"explain {i}: no .q")
    for i, q in enumerate(soup.select(".ts-predict"), 1):
        if not q.select_one(".ts-reveal"):
            E(f"predict {i}: no .ts-reveal")
        if not q.select_one(".q"):
            E(f"predict {i}: no .q")
        check_claim_refs(q, f"predict {i}")

    # ---- figures ----
    for i, f in enumerate(soup.select(".ts-seq, .ts-graph"), 1):
        what = f"figure {i} ({f.get('data-title', '')})"
        s = f.find("script", attrs={"type": "application/json"})
        try:
            spec = json.loads(s.string)
        except Exception as e:  # noqa
            E(f"{what}: bad JSON {e}")
            continue
        if "ts-seq" in f.get("class", []):
            act = [a["id"] for a in spec.get("actors", [])]
            if len(act) != len(set(act)):
                E(f"{what}: duplicate actor ids")
            for st in spec.get("steps", []):
                for k in ("from", "to"):
                    if k in st and st[k] not in act:
                        E(f"{what}: step refers to unknown actor {st[k]}")
                for o in [st["over"]] if isinstance(st.get("over"), str) else st.get("over", []):
                    if o not in act:
                        E(f"{what}: note over unknown actor {o}")
                if not st.get("note"):
                    W(f"{what}: step '{st.get('label', '')[:40]}' has no note (caption)")
        else:
            nodes = [n["id"] for n in spec.get("nodes", [])]
            for e in spec.get("edges", []):
                if e.get("from") not in nodes or e.get("to") not in nodes:
                    E(f"{what}: edge {e} refers to unknown node")
            mx = max([x.get("step", 0) for x in spec.get("nodes", []) + spec.get("edges", [])] or [0])
            if mx and len(spec.get("captions", [])) != mx:
                E(f"{what}: {mx} steps but {len(spec.get('captions', []))} captions")
            pos = [(n.get("col", 0), n.get("row", 0)) for n in spec.get("nodes", [])]
            if len(pos) != len(set(pos)):
                E(f"{what}: two nodes share a grid cell")

    # ---- code ----
    for i, c in enumerate(soup.select(".ts-code"), 1):
        v = c.get("data-verified")
        if v not in ("ran", "spec"):
            E(f"code block {i}: data-verified must be 'ran' (tested) or 'spec' (names backed by claims)")
        if v == "ran" and not c.get("data-file"):
            E(f"code block {i}: 'ran' code must come from examples/<slug>/ via data-file, so tests cover it")
        if v == "spec":
            check_claim_refs(c, f"code block {i}")

    # ---- terms ----
    for d in soup.find_all("dfn"):
        if not d.get("data-def"):
            E(f"<dfn>{d.get_text()}</dfn> has no data-def")

    # ---- external resources (a canonical link is metadata, not a fetched resource) ----
    for t in soup.find_all(["script", "link", "img", "iframe", "audio", "video", "source"]):
        if t.name == "link" and "canonical" in (t.get("rel") or []):
            continue
        ref = t.get("src") or (t.get("href") if t.name == "link" else None)
        if ref and re.match(r"^(https?:)?//", ref):
            E(f"external resource not allowed (no third-party requests): <{t.name} {ref}>")

    counts = f"{len(parts)} parts; {len(claims)} claims; {len(sources)} sources"
    print(f"{p}: {len(errors)} error(s), {len(warns)} warning(s); {counts}")
    for e in errors:
        print("ERROR  " + e)
    for w in warns:
        print("WARN   " + w)
    if errors or (strict and warns):
        sys.exit(1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    target = Path(args[0])
    if not target.suffix:  # a slug
        target = Path(__file__).resolve().parent.parent / "site" / args[0] / "index.html"
    main(str(target), "--strict" in sys.argv)

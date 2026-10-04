#!/usr/bin/env python3
"""Build the deepstack site from content/, examples/ and ui/ into site/.

Usage (from the project root):
  uv run tools/build.py all            # rebuild every topic and the index (default)
  uv run tools/build.py topic <slug>   # rebuild one topic and the index
  uv run tools/build.py index          # rebuild only the index

Layout:
  content/<slug>/meta.json, body.html, ledger.json   lesson source (what Claude writes)
  examples/<slug>/*.py                                runnable code, tested by pytest
  ui/ts.css, ui/ts.js, ui/templates/*.html            shared design system and page shells
  site.json                                           site name, public URL, author, licenses
  site/                                               generated output (deployed to GitHub Pages)

A code block written as <div class="ts-code" data-file="client.py" ...></div> is filled with
examples/<slug>/client.py at build time, so the page always shows the exact code the tests ran.

Prints every file it writes as "WROTE <path relative to the project root>".
Exit codes: 0 ok, 2 bad input, 3 site/index.html exists but was not made by this tool.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT, EXAMPLES, UI, SITE = ROOT / "content", ROOT / "examples", ROOT / "ui", ROOT / "site"
CFG = json.loads((ROOT / "site.json").read_text())
RUNGS = {
    0: "Before you start",
    1: "Why it exists",
    2: "How it works",
    3: "Using it",
    4: "When it breaks",
    5: "When to pick it",
}
MARKER = 'content="teach-site'
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
PART_RE = re.compile(r'<section\s+class="ts-part"([^>]*)>(.*?)</section>', re.S)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
CODE_FILE_RE = re.compile(r'(<div class="ts-code"[^>]*\bdata-file="([^"]+)"[^>]*>)\s*(</div>)')


def die(msg: str, code: int = 2) -> None:
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    path.write_text(text)
    print("WROTE " + str(path.relative_to(ROOT)))


def embed_json(obj: object) -> str:
    """JSON that is safe inside <script type="application/json">."""
    return json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/")


def guard_site() -> None:
    idx = SITE / "index.html"
    if idx.exists() and MARKER not in idx.read_text(errors="ignore")[:2000]:
        die(f"{idx} exists and was not made by teach-site. Ask the user before touching it.", 3)


def copy_ui() -> None:
    for name in ("ts.css", "ts.js", "theme.js", "favicon.svg"):
        write(SITE / "_ts" / name, (UI / name).read_text())


def license_foot() -> str:
    c, k = CFG["content_license"], CFG["code_license"]
    return (
        f'<p class="ts-foot">© {html.escape(CFG["year"])} {html.escape(CFG["author"])}. '
        f'Lesson text: <a href="{c["url"]}" rel="license">{html.escape(c["name"])}</a>. '
        f'Code: <a href="{k["url"]}" rel="license">{html.escape(k["name"])}</a>. '
        f'Source: <a href="{CFG["repo_url"]}">{html.escape(CFG["repo_url"].removeprefix("https://"))}</a>.</p>'
    )


def fill_common(text: str, canonical: str) -> str:
    return (
        text.replace("{{SITE_NAME}}", html.escape(CFG["name"]))
        .replace("{{AUTHOR}}", html.escape(CFG["author"]))
        .replace("{{CANONICAL}}", canonical)
        .replace("{{LICENSE_FOOT}}", license_foot())
    )


def parse_parts(body: str) -> list[dict]:
    parts = []
    for i, m in enumerate(PART_RE.finditer(body), 1):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        h2 = H2_RE.search(m.group(2))
        if not h2:
            die(f"part {i} has no <h2>")
        parts.append(
            {
                "id": attrs.get("id") or f"p{i}",
                "rung": int(attrs.get("data-rung", "1")),
                "min": int(attrs.get("data-min", "0") or 0),
                "title": html.unescape(TAG_RE.sub("", h2.group(1))).strip(),
            }
        )
    if not parts:
        die('body.html has no <section class="ts-part"> elements')
    return parts


def inline_code(slug: str, body: str) -> str:
    def fill(m: re.Match) -> str:
        src = EXAMPLES / slug / m.group(2)
        if not src.is_file():
            die(f"code block refers to {src.relative_to(ROOT)}, which does not exist")
        code = html.escape(src.read_text().rstrip("\n"), quote=False)
        return f"{m.group(1)}\n<pre><code>{code}</code></pre>\n{m.group(3)}"

    return CODE_FILE_RE.sub(fill, body)


def load_topic(slug: str) -> dict:
    d = CONTENT / slug
    for f in ("meta.json", "body.html", "ledger.json"):
        if not (d / f).is_file():
            die(f"missing {(d / f).relative_to(ROOT)}")
    meta = json.loads((d / "meta.json").read_text())
    for k in ("slug", "title", "tldr", "category", "created"):
        if not meta.get(k):
            die(f"{slug}/meta.json needs '{k}'")
    if meta["slug"] != slug or not SLUG_RE.fullmatch(slug):
        die(f"slug '{meta['slug']}' must equal its folder name and use a-z, 0-9 and hyphens")
    ledger = json.loads((d / "ledger.json").read_text())
    body = inline_code(slug, (d / "body.html").read_text())
    return {"meta": meta, "ledger": ledger, "body": body, "parts": parse_parts(body)}


def all_slugs() -> list[str]:
    return (
        sorted(p.name for p in CONTENT.iterdir() if (p / "meta.json").is_file()) if CONTENT.exists() else []
    )


def build_topic(slug: str, known: set[str]) -> None:
    t = load_topic(slug)
    meta, ledger, parts = t["meta"], t["ledger"], t["parts"]
    minutes = sum(p["min"] for p in parts)
    verified = ledger.get("verified") or dt.date.today().isoformat()
    n_src = len(ledger.get("sources", []))
    n_claims = len([c for c in ledger.get("claims", []) if c.get("status") == "verified"])

    counts = {r: sum(p["rung"] == r for p in parts) for r in sorted({p["rung"] for p in parts})}
    route = "".join(
        f'<li data-rung="{r}">{RUNGS[r]} <span class="ts-route-n">({n})</span></li>'
        for r, n in counts.items()
    )
    meta_line = "".join(
        [
            f"<span><b>{len(parts)}</b> parts</span>",
            f"<span>about <b>{minutes}</b> min</span>" if minutes else "",
            f"<span>Aimed at <b>{html.escape(meta.get('level', 'senior backend engineer'))}</b></span>",
            f"<span><b>{n_claims}</b> facts checked against <b>{n_src}</b> sources on "
            f"<b>{html.escape(verified)}</b></span>",
        ]
    )

    def link(item: dict, suffix: str = "") -> str:
        label, s = html.escape(item.get("label", "")), item.get("slug")
        return f'<a href="../{s}/index.html">{label}</a>' if s in known else label + suffix

    prereqs = ""
    if meta.get("prereqs"):
        prereqs = (
            '<p class="ts-meta ts-resume">You should know first:&nbsp;'
            + ", ".join(link(p) for p in meta["prereqs"])
            + "</p>"
        )
    related = []
    for r in meta.get("related", []):
        why = html.escape(r.get("why", ""))
        tail = "" if r.get("slug") in known else ' <span class="ts-muted">(not covered yet)</span>'
        related.append(f"<li>{link(r)}{': ' + why if why else ''}{tail}</li>")
    nextup = (
        f"<ul>{''.join(related)}</ul>"
        if related
        else "<p>You have the full route. Press V in a day to review.</p>"
    )

    page_meta = {k: meta.get(k) for k in ("slug", "title", "tldr", "category", "level")}
    out = (
        fill_common((UI / "templates" / "topic.html").read_text(), f"{CFG['site_url']}/{slug}/")
        .replace("{{TITLE}}", html.escape(meta["title"]))
        .replace("{{SLUG}}", slug)
        .replace("{{TLDR}}", html.escape(meta["tldr"]))
        .replace("{{ROUTE}}", route)
        .replace("{{META_LINE}}", meta_line)
        .replace("{{PREREQS}}", prereqs)
        .replace("{{NEXTUP}}", nextup)
        .replace("{{GENERATED}}", verified)
        .replace("{{META_JSON}}", embed_json(page_meta))
        .replace("{{LEDGER_JSON}}", embed_json(ledger))
        .replace("{{BODY}}", t["body"])
    )
    write(SITE / slug / "index.html", out)


def build_index() -> None:
    topics = []
    for slug in all_slugs():
        t = load_topic(slug)
        m, parts = t["meta"], t["parts"]
        topics.append(
            {
                "slug": slug,
                "title": m["title"],
                "tldr": m["tldr"],
                "category": m["category"],
                "minutes": sum(p["min"] for p in parts),
                "created": m["created"],
                "verified": t["ledger"].get("verified"),
                "parts": [{"id": p["id"], "rung": p["rung"]} for p in parts],
            }
        )
    n = len(topics)
    count = "No topics yet." if n == 0 else f"{n} topic{'s' if n != 1 else ''}."
    out = (
        fill_common((UI / "templates" / "index.html").read_text(), f"{CFG['site_url']}/")
        .replace("{{TOPICS_JSON}}", embed_json({"generator": "teach-site", "topics": topics}))
        .replace("{{COUNT_LINE}}", count)
    )
    write(SITE / "index.html", out)


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "all"
    guard_site()
    copy_ui()
    known = set(all_slugs())
    if cmd == "all":
        for slug in sorted(known):
            build_topic(slug, known)
    elif cmd == "topic" and len(argv) == 2:
        if argv[1] not in known:
            die(f"no content/{argv[1]}/meta.json")
        build_topic(argv[1], known)
    elif cmd != "index":
        die(__doc__ or "")
    build_index()


if __name__ == "__main__":
    main(sys.argv[1:])

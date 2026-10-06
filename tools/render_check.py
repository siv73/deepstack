#!/usr/bin/env python3
"""Render, interaction and accessibility checks for a lesson page, in headless Chromium.

Usage (from the project root): uv run tools/render_check.py <slug>

Checks site/<slug>/index.html and site/index.html at phone (390px) and desktop (1280px) widths,
in light and dark mode:
  - no console errors or uncaught exceptions
  - no sideways page scroll
  - every diagram renders and its stepper reaches the last step
  - every quiz accepts its answer key; every ordering exercise accepts the correct order
  - predict and explain-back reveals work; focus, recap and review modes toggle
  - no serious or critical accessibility violations (axe-core from node_modules, if installed)
Pages are served over local HTTP, as on GitHub Pages, with their Content-Security-Policy enforced:
any CSP violation shows up as a console error and fails the check.
Screenshots go to _render/<slug>/ for you to look at.

Browser: Playwright's Chromium (install once: uv run playwright install chromium).
Set TS_CHROME to use another Chrome binary instead. Exit 0 = pass, 1 = failures.
"""

from __future__ import annotations

import functools
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
AXE = ROOT / "node_modules" / "axe-core" / "axe.min.js"
CHROME_ARGS = [
    "--no-sandbox",
    "--disable-background-networking",
    "--disable-component-update",
    "--no-first-run",
]
VIEWS = ((390, 844, "phone"), (1280, 860, "desktop"))


def collect_errors(page: Page) -> list[str]:
    errs: list[str] = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    return errs


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


def serve(directory: Path) -> tuple[ThreadingHTTPServer, str]:
    """Serve site/ on a free localhost port, mounted under /<site name>/ like GitHub Pages."""
    handler = functools.partial(QuietHandler, directory=str(directory))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def axe_violations(page: Page) -> list[str]:
    if not AXE.exists():
        return []
    # Evaluated through the DevTools protocol, so the page's CSP (no inline scripts) still holds.
    page.evaluate(AXE.read_text())
    result = page.evaluate(
        "async () => (await axe.run(document, {resultTypes: ['violations']})).violations"
        ".filter(v => ['serious', 'critical'].includes(v.impact))"
        ".map(v => v.id + ' (' + v.impact + '): ' + v.help + ' x' + v.nodes.length)"
    )
    return list(result)


def exercise_page(page: Page, out: Path, fails: list[str]) -> None:
    for i in range(page.locator(".ts-fig").count()):
        fig = page.locator(".ts-fig").nth(i)
        if fig.locator(".ts-fig-ctl").count() == 0:
            continue
        fig.scroll_into_view_if_needed()
        total = int(fig.locator(".ts-fig-count").inner_text().split("of")[-1])
        for _ in range(total):
            fig.get_by_role("button", name="Next step").click()
        if fig.locator(".ts-fig-count").inner_text() != f"Step {total} of {total}":
            fails.append(f"diagram {i + 1}: stepper did not reach the last step")
        fig.screenshot(path=str(out / f"fig-{i + 1}-last-step.png"))
    quizzes = page.locator(".ts-quiz")
    for i in range(quizzes.count()):
        q = quizzes.nth(i)
        ans = (q.get_attribute("data-answer") or "").upper()
        q.scroll_into_view_if_needed()
        q.locator(".ts-opts button", has=page.locator(".key", has_text=ans)).first.click()
        if q.locator("button.is-right").count() != 1 or q.locator(".ts-feedback b.ok").count() != 1:
            fails.append(f"quiz {i + 1}: answer key {ans} was not accepted")
    orders = page.locator(".ts-order")
    for i in range(orders.count()):
        o = orders.nth(i)
        o.scroll_into_view_if_needed()
        for k in range(o.locator(".ts-order-list button").count()):
            o.locator(f".ts-order-list button[data-i='{k}']").click()
        o.get_by_role("button", name="Check order").click()
        if o.locator(".ts-feedback b.ok").count() != 1:
            fails.append(f"order {i + 1}: the correct order was not accepted")
    for i in range(page.locator(".ts-predict").count()):
        p = page.locator(".ts-predict").nth(i)
        p.get_by_role("button", name="No idea, show me").click()
        if not p.locator(".ts-reveal").is_visible():
            fails.append(f"predict {i + 1}: reveal did not show")
    for i in range(page.locator(".ts-explain").count()):
        e = page.locator(".ts-explain").nth(i)
        e.get_by_role("button", name="Check myself").click()
        if not e.locator(".ts-model").is_visible():
            fails.append(f"explain {i + 1}: model answer did not show")
    page.screenshot(path=str(out / "topic-desktop-light-answered.png"), full_page=True)
    for key, name in (("f", "focus"), ("f", None), ("r", "recap"), ("r", None), ("v", "review"), ("v", None)):
        page.locator("body").press(key)
        page.wait_for_timeout(150)
        if name:
            page.screenshot(path=str(out / f"mode-{name}.png"), full_page=name != "focus")
    done = page.locator(".ts-done-row .ts-btn").first
    done.scroll_into_view_if_needed()
    done.click()
    if "Done" not in done.inner_text():
        fails.append("the mark-done button did not toggle")


def main(slug: str) -> None:
    topic = ROOT / "site" / slug / "index.html"
    index = ROOT / "site" / "index.html"
    if not topic.exists():
        print(f"ERROR: {topic} not found; run tools/build.py first")
        sys.exit(2)
    out = ROOT / "_render" / slug
    out.mkdir(parents=True, exist_ok=True)
    fails: list[str] = []
    httpd, base = serve(ROOT / "site")
    with sync_playwright() as p:
        exe = os.environ.get("TS_CHROME")
        browser = p.chromium.launch(executable_path=exe, args=CHROME_ARGS) if exe else p.chromium.launch()
        for scheme in ("light", "dark"):
            for w, h, tag in VIEWS:
                label = f"{tag}/{scheme}"
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme)
                page = ctx.new_page()
                errs = collect_errors(page)
                for name, path in (("topic", topic), ("index", index)):
                    page.goto(f"{base}/{path.relative_to(ROOT / 'site').as_posix()}")
                    page.wait_for_timeout(400)
                    width = page.evaluate("document.documentElement.scrollWidth")
                    if width > w + 1:
                        fails.append(f"{label} {name}: page scrolls sideways ({width}px wide at {w}px)")
                    if name == "topic":
                        rendered = page.evaluate(
                            "[...document.querySelectorAll('.ts-fig')].map(f => !!f.querySelector('svg'))"
                        )
                        if not all(rendered):
                            fails.append(f"{label}: {rendered.count(False)} diagram(s) failed to render")
                    elif page.locator(f".ix-item a[href='{slug}/index.html']").count() != 1:
                        fails.append(f"{label} index: no link to {slug}")
                    page.screenshot(path=str(out / f"{name}-{tag}-{scheme}.png"), full_page=True)
                    if tag == "desktop":
                        before = len(errs)
                        fails += [f"{label} {name}: a11y {v}" for v in axe_violations(page)]
                        del errs[before:]  # axe's own probes are not page errors
                    if name == "topic" and tag == "desktop" and scheme == "light":
                        exercise_page(page, out, fails)
                if tag == "phone":
                    # Fonts differ between machines (CI vs local); a 320px pass leaves headroom at 390px.
                    page.set_viewport_size({"width": 320, "height": h})
                    page.goto(f"{base}/{topic.relative_to(ROOT / 'site').as_posix()}")
                    page.wait_for_timeout(300)
                    width = page.evaluate("document.documentElement.scrollWidth")
                    if width > 321:
                        fails.append(f"{label} topic: page scrolls sideways at 320px ({width}px wide)")
                fails += [f"{label}: console error: {e}" for e in errs]
                ctx.close()
        browser.close()
    httpd.shutdown()
    print(f"screenshots: {out.relative_to(ROOT)}")
    if not AXE.exists():
        print("NOTE  accessibility not checked: run `npm ci` to install axe-core")
    for f in fails:
        print("FAIL  " + f)
    if fails:
        sys.exit(1)
    print("PASS  render, interaction and accessibility checks")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])

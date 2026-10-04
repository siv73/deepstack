# deepstack

Backend engineering topics, taken from zero to senior-engineer depth: why each
thing exists, how it works, how to use it, how it breaks, and when to pick it.

**Read it:** https://siv73.github.io/deepstack

Every page is:

- **Fact-checked.** Each factual claim was read in an official source and
  confirmed in a second, separate read. The sources are listed on the page.
- **Tested.** Every code sample on a page is a file in `examples/` with pytest
  tests that prove the behaviour the page describes.
- **Interactive.** Step-through diagrams, quizzes and explain-back prompts, with
  progress saved in your browser.

Pages are written with Claude (Anthropic) and reviewed by me.

## Layout

| Folder | What it holds |
|---|---|
| `content/<topic>/` | Lesson source: `meta.json`, `body.html`, `ledger.json` (every fact and its sources) |
| `examples/<topic>/` | Runnable code shown on the page, with pytest tests |
| `ui/` | Shared design system (`ts.css`), runtime (`ts.js`, `theme.js`), page templates |
| `tools/` | `build.py`, `verify_page.py`, `render_check.py` |
| `site.json` | Site name, public URL, author, licenses |
| `authoring/` | How lessons are researched, written and checked |

`site/` is generated and deployed by CI; it is not committed.

## Run it locally

Needs [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
make setup                   # uv sync + npm ci + Chromium for browser checks
make build                   # build site/ from content/, examples/, ui/
make check                   # build, tests, lint, and page checks for every topic
make check-page SLUG=oauth   # one topic
```

Python runs only in the project's uv environment; UI tools only from
`node_modules/`. Nothing installs globally.

## Deploys

Every push to `main` runs `.github/workflows/site.yml`: it installs from
lockfiles, runs `make check`, and deploys `site/` to GitHub Pages only if every
check passes.

## License

- Lesson content: [CC BY-NC-SA 4.0](LICENSE-CONTENT.md). Credit required, no commercial use.
- Code: [MIT](LICENSE).

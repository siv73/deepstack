# deepstack: one command per job. Run `make help` for the list.
SLUG ?=

.PHONY: help setup build test lint format check-page check open

help:
	@echo "make setup               install Python (uv) and UI (npm) tooling, plus the test browser"
	@echo "make build               rebuild site/ from content/, examples/ and ui/"
	@echo "make test                run every topic's example tests"
	@echo "make lint                lint and format-check Python (ruff) and UI (biome, html-validate)"
	@echo "make format              auto-format Python and UI source"
	@echo "make check-page SLUG=x   fact/structure checks and browser checks for one topic"
	@echo "make check               everything: build, test, lint, and check-page for every topic"
	@echo "make open                serve site/ on localhost:8000 and open it"

setup:
	uv sync
	npm ci
	uv run playwright install chromium

build:
	uv run tools/build.py all

# Each topic's examples run in their own process so module names can't clash across topics.
test:
	@for d in examples/*/; do echo "== $$d"; uv run pytest "$$d" || exit 1; done

lint: build
	uv run ruff check .
	uv run ruff format --check .
	npm run check

format:
	uv run ruff format .
	uv run ruff check --fix .
	npx biome check --write ui

check-page:
	@test -n "$(SLUG)" || (echo "usage: make check-page SLUG=<topic>" && exit 2)
	uv run tools/verify_page.py $(SLUG)
	uv run tools/render_check.py $(SLUG)

check: build test lint
	@for d in content/*/; do $(MAKE) --no-print-directory check-page SLUG=$$(basename $$d) || exit 1; done

open: build
	uv run python -m http.server -d site 8000 & sleep 1; open http://localhost:8000

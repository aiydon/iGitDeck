SHELL := /bin/bash
.DEFAULT_GOAL := help

export PATH := $(CURDIR)/bin:$(PATH)

.PHONY: help install scc env types build run api-dev web-dev crawler crawl-once import-user test lint format typecheck hooks clean

help:
	@printf '%s\n' \
		'  make install    Install Python + frontend deps, scc, env, build assets' \
		'  make build      Generate API types and build frontend' \
		'  make run        Run the FastAPI service (uvicorn)' \
		'  make crawler    Run the GitHub Trending crawler loop' \
		'  make crawl-once Run one crawler pass' \
		'  make import-user GITHUB_USER=<name>  Import all public GitHub repos of a user' \
		'  make test       Run the backend test suite' \
		'  make lint       Ruff check + frontend typecheck' \
		'  make format     Ruff format/fix' \
		'  make hooks      Install the optional commit-msg hook' \
		'  make api-dev    Backend with reload (port 8000)' \
		'  make web-dev    Vite dev server (proxies /api and /git)' \
		'  make clean      Remove caches and build artifacts'

install:
	uv sync
	cd frontend && bun install
	$(MAKE) scc
	@test -f .env || cp .env.example .env
	$(MAKE) build

scc:
	@if command -v scc >/dev/null 2>&1; then \
		echo "using $$(command -v scc)"; \
	elif [ -x bin/scc ]; then \
		echo "using $(CURDIR)/bin/scc"; \
	else \
		uv run python scripts/install_scc.py; \
	fi

env:
	@test -f .env || cp .env.example .env

types:
	uv run python -m igitdeck.openapi > frontend/openapi.json
	cd frontend && bun run generate:api

build: types
	cd frontend && bun run build

run:
	uv run igitdeck

api-dev:
	uv run uvicorn --factory igitdeck.main:create_app --reload --host 127.0.0.1 --port 8000

web-dev:
	cd frontend && bun run dev

crawler:
	uv run python -m igitdeck.crawler

crawl-once:
	uv run python -m igitdeck.crawler --once

import-user:
	@test -n "$(GITHUB_USER)" || { echo "用法: make import-user GITHUB_USER=<github-username>"; exit 1; }
	uv run python -m igitdeck.crawler.github_user "$(GITHUB_USER)"

test:
	uv run pytest

lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	$(MAKE) typecheck

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck: types
	cd frontend && bun run typecheck

hooks:
	git config core.hooksPath .githooks

clean:
	rm -rf .pytest_cache .ruff_cache frontend/dist frontend/openapi.json frontend/src/api/schema.d.ts

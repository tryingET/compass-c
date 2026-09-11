set shell := ["bash", "-euo", "pipefail", "-c"]

default: help

help:
    @just --list

test:
    uv run --extra dev python -m pytest tests/ -v --tb=short

# Real subprocess transport using the lockfile-selected SDK; no model or network host.
test-mcp:
    uv run --frozen --extra dev --extra mcp python -m pytest tests/test_mcp_live.py -v --tb=short

# Linux opt-in: isolated HOME and network namespace; requires local Pi and Codex.
# Set PI_CODING_AGENT_PACKAGE to the reviewed installed Pi package directory.
dogfood-hosts:
    test -n "${PI_CODING_AGENT_PACKAGE:?Set the installed Pi package directory}"
    COMPASS_HOST_DOGFOOD=1 uv run --frozen --extra dev python -m pytest tests/test_host_dogfood.py -v --tb=short

check:
    uv run --extra dev ruff format --check .
    uv run --extra dev ruff check .
    uv run --extra dev python scripts/build_skill.py --check
    uv run --extra dev python scripts/validate_skill.py

build:
    uv run --extra dev python -m build
    uv run --extra dev python scripts/build_archives.py --sync-plugin
    uv run --extra dev python scripts/build_archives.py

lint:
    uv run --extra dev ruff check .

fmt:
    uv run --extra dev ruff format .
    uv run --extra dev ruff check --fix .

ci:
    ./scripts/ci/full.sh

run:
    uv run compass-c --help

doctor:
    @uv --version
    @uv run python --version
    @git --version
    @just --version

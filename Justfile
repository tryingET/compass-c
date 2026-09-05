set shell := ["bash", "-euo", "pipefail", "-c"]

default: help

help:
    @just --list

test:
    uv run --extra dev python -m pytest tests/ -v --tb=short

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

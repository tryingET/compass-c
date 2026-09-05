#!/bin/sh
set -eu

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH='' cd -- "$script_dir/../.." && pwd)"
cd "$repo_root"

"$script_dir/smoke.sh"
uv run --extra dev ruff format --check .
uv run --extra dev ruff check .
uv run --extra dev python scripts/build_skill.py --check
uv run --extra dev python scripts/validate_skill.py
uv run --extra dev python -m pytest tests/ -q
./scripts/check-document-policy.sh

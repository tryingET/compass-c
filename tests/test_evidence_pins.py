"""Retained evaluation evidence pins exact code bytes; formatters must not rewrite them."""

from __future__ import annotations

import hashlib
import json
import tomllib
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pinned_jury_code_is_unchanged_and_excluded_from_ruff() -> None:
    result = json.loads(
        (ROOT / "evals/dspx-jury/subscription-result.json").read_text(encoding="utf-8")
    )
    pins = result["code_sha256"]
    assert len(pins) == 9
    ruff = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"]
    excluded = ruff.get("extend-exclude", [])
    for relative, digest in pins.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest, relative
        if relative.endswith(".py"):
            assert any(fnmatch(relative, pattern) for pattern in excluded), relative

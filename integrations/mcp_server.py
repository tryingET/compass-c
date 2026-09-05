#!/usr/bin/env python3
"""Optional local stdio MCP adapter for COMPASS-C.

This adapter is provisional until a live SDK round-trip passes. Do not expose it as
a shared service without authentication, tenant isolation, quotas, and retention policy.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from compass_c import VERSION, CompassError, Notebook, calculate

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit("Install the optional dependency: uv sync --extra mcp") from exc

mcp = FastMCP(
    "COMPASS-C",
    instructions=(
        f"COMPASS-C {VERSION}. Advisory records and conditional calculations only; "
        "no result grants action permission."
    ),
)
_book: Notebook | None = None


def notebook() -> Notebook:
    global _book
    if _book is None:
        path = os.environ.get("COMPASS_DB", str(Path.home() / ".compass" / "decisions.sqlite3"))
        _book = Notebook(path)
    return _book


def result(function: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "data": function(*args, **kwargs)}
    except CompassError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}


@mcp.tool()
def compass_start(
    objective: str, stakes: str = "medium", constraints: list[str] | None = None
) -> dict[str, Any]:
    """Create a local decision record; this does not authorize external action."""
    return result(notebook().start, objective, stakes, constraints)


@mcp.tool()
def compass_get(decision_id: str) -> dict[str, Any]:
    """Read a local record, including revision and invalidation history."""
    return result(notebook().get, decision_id)


@mcp.tool()
def compass_record(
    decision_id: str,
    expected_revision: int,
    kind: str,
    content: str,
    status: str = "proposed",
    source: str = "",
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    """Append a typed local note with optimistic revision checking."""
    return result(
        notebook().record,
        decision_id,
        expected_revision,
        kind,
        content,
        status,
        source,
        depends_on,
    )


@mcp.tool()
def compass_review(decision_id: str) -> dict[str, Any]:
    """Run a structural review; completeness is not truth, safety, or permission."""
    return result(notebook().review, decision_id)


@mcp.tool()
def compass_invalidate(
    decision_id: str, expected_revision: int, note_id: str, reason: str
) -> dict[str, Any]:
    """Mark a note and dependent conclusions stale while retaining history."""
    return result(notebook().invalidate, decision_id, expected_revision, note_id, reason)


@mcp.tool()
def compass_calculate(kind: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Run a bounded conditional calculation without creating notebook state."""
    return result(calculate, kind, parameters)


if __name__ == "__main__":
    mcp.run(transport="stdio")

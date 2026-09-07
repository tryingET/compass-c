"""Optional local stdio MCP adapter for the installed COMPASS-C package.

The pinned SDK and wheel are exercised by actual local client round-trips. This
does not prove installation, discovery, or usefulness in a vendor's host. The
adapter is local only; it is not an authenticated shared-service profile.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import VERSION, CompassError, Notebook, calculate

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
    from pydantic import StrictInt
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit("Install the optional dependency: pip install 'compass-c[mcp]'") from exc

mcp = MCPServer(
    "COMPASS-C",
    version=VERSION,
    instructions=(
        f"COMPASS-C {VERSION}. Advisory records and conditional calculations only; "
        "no result grants action permission. Local notebook changes require the "
        "current revision; reread after a conflict instead of blindly retrying."
    ),
)
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
LOCAL_WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)


def result(function: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Keep domain and storage failures in the same envelope as the CLI."""
    try:
        return {"ok": True, "data": function(*args, **kwargs)}
    except CompassError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
    except (OSError, sqlite3.Error):
        return {
            "ok": False,
            "error": {"code": "STORAGE_ERROR", "message": "Unable to access COMPASS-C notebook"},
        }


def notebook_result(method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        path = os.environ.get("COMPASS_DB", str(Path.home() / ".compass" / "decisions.sqlite3"))
        return getattr(Notebook(path), method)(*args, **kwargs)

    return result(operation)


@mcp.tool(annotations=LOCAL_WRITE)
def compass_start(
    objective: str, stakes: str = "medium", constraints: list[str] | None = None
) -> dict[str, Any]:
    """Create a local decision record; this does not authorize external action."""
    return notebook_result("start", objective, stakes, constraints)


@mcp.tool(annotations=READ_ONLY)
def compass_get(decision_id: str) -> dict[str, Any]:
    """Read a local record, including revision and invalidation history."""
    return notebook_result("get", decision_id)


@mcp.tool(annotations=READ_ONLY)
def compass_list(limit: StrictInt = 20, offset: StrictInt = 0) -> dict[str, Any]:
    """Recover existing decision IDs with bounded pagination before creating duplicates."""
    return notebook_result("list", limit, offset)


@mcp.tool(annotations=READ_ONLY)
def compass_brief(decision_id: str) -> dict[str, Any]:
    """Inspect recommendations, provenance, uncertainty, reversals, and stale history."""
    return notebook_result("brief", decision_id)


@mcp.tool(annotations=LOCAL_WRITE)
def compass_record(
    decision_id: str,
    expected_revision: StrictInt,
    kind: str,
    content: str,
    status: str = "proposed",
    source: str = "",
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    """Append a typed local note with optimistic revision checking."""
    return notebook_result(
        "record",
        decision_id,
        expected_revision,
        kind,
        content,
        status,
        source,
        depends_on,
    )


@mcp.tool(annotations=LOCAL_WRITE)
def compass_revise(
    decision_id: str,
    expected_revision: StrictInt,
    note_id: str,
    content: str,
    reason: str,
    status: str = "proposed",
    source: str = "",
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    """Replace evidence while preserving history and invalidating dependent conclusions."""
    return notebook_result(
        "revise",
        decision_id,
        expected_revision,
        note_id,
        content,
        reason,
        status,
        source,
        depends_on,
    )


@mcp.tool(annotations=READ_ONLY)
def compass_review(decision_id: str) -> dict[str, Any]:
    """Run a structural review; completeness is not truth, safety, or permission."""
    return notebook_result("review", decision_id)


@mcp.tool(annotations=LOCAL_WRITE)
def compass_invalidate(
    decision_id: str, expected_revision: StrictInt, note_id: str, reason: str
) -> dict[str, Any]:
    """Mark a note and dependent conclusions stale while retaining history."""
    return notebook_result("invalidate", decision_id, expected_revision, note_id, reason)


@mcp.tool(annotations=LOCAL_WRITE)
def compass_migrate() -> dict[str, Any]:
    """Explicitly upgrade a supported existing notebook without rewriting its decisions."""
    return notebook_result("migrate")


@mcp.tool(annotations=READ_ONLY)
def compass_calculate(kind: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Run a bounded conditional calculation without creating notebook state."""
    return result(calculate, kind, parameters)


def main() -> None:
    """Start the supported local stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

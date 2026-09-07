"""BDD acceptance for an actual SDK client/server stdio connection.

Set COMPASS_MCP_PYTHON to a wheel-only environment's Python to verify the installed
distribution with these same scenarios. These are local SDK tests, not vendor-host
installation, discovery, or behavioral-improvement evidence.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = os.environ.get("COMPASS_MCP_PYTHON", sys.executable)
sdk = pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="requires the mcp extra")
TOOLS = {
    "compass_start",
    "compass_get",
    "compass_record",
    "compass_review",
    "compass_invalidate",
    "compass_calculate",
    "compass_brief",
    "compass_revise",
    "compass_list",
    "compass_migrate",
}
READ_ONLY = {"compass_get", "compass_review", "compass_calculate", "compass_brief", "compass_list"}


@asynccontextmanager
async def session(path: Path, cwd: Path) -> AsyncIterator[Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    parameters = StdioServerParameters(
        command=PYTHON,
        args=["-I", "-B", "-m", "compass_c.mcp_server"],
        cwd=str(cwd),
        env={"COMPASS_DB": str(path)},
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=15) as client:
            initialized = await client.initialize()
            assert "no result grants action permission" in initialized.instructions
            yield client


async def call(client: Any, name: str, **arguments: Any) -> dict[str, Any]:
    response = await client.call_tool(name, arguments)
    assert not response.is_error, response
    assert type(response.structured_content) is dict, response
    payload = response.structured_content
    texts = [item.text for item in response.content if item.type == "text"]
    assert len(texts) == 1
    assert json.loads(texts[0]) == payload
    if payload["ok"]:
        assert payload["data"]["action_permission"] == "not_granted"
    else:
        assert set(payload) == {"ok", "error"}
        assert set(payload["error"]) == {"code", "message"}
        assert "Traceback" not in payload["error"]["message"]
    return payload


def test_mcp_configuration_invokes_installed_module_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "decisions.sqlite3"
    process = subprocess.run(
        [PYTHON, str(ROOT / "scripts/configure_mcp.py"), "--db", str(path)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert process.returncode == 0, process.stderr
    config = json.loads(process.stdout)["mcpServers"]["compass"]
    assert config["args"] == ["-m", "compass_c.mcp_server"]
    assert Path(config["command"]).is_file()
    assert config["env"] == {"COMPASS_DB": str(path)}
    assert not path.parent.exists()


def test_installed_distribution_exposes_mcp_console_entrypoint(tmp_path: Path) -> None:
    process = subprocess.run(
        [
            PYTHON,
            "-I",
            "-c",
            "import importlib.metadata as m; "
            "print(next((e.value for e in m.distribution('compass-c').entry_points "
            "if e.name == 'compass-c-mcp'), 'missing'))",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "compass_c.mcp_server:main"


@sdk
def test_sdk_initializes_and_discovers_tools_without_creating_storage(tmp_path: Path) -> None:
    import anyio

    path = tmp_path / "missing" / "decisions.sqlite3"

    async def scenario() -> None:
        async with session(path, tmp_path) as client:
            discovered = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert set(discovered) == TOOLS
            for name, tool in discovered.items():
                assert tool.annotations.read_only_hint is (name in READ_ONLY)
                assert tool.annotations.open_world_hint is False
            await client.send_ping()
        assert not path.parent.exists()

    anyio.run(scenario)


@sdk
def test_sdk_calculates_and_returns_domain_errors_without_creating_storage(tmp_path: Path) -> None:
    import anyio

    path = tmp_path / "missing" / "decisions.sqlite3"

    async def scenario() -> None:
        async with session(path, tmp_path) as client:
            score = await call(
                client,
                "compass_calculate",
                kind="brier",
                parameters={"probabilities": [0.8], "outcomes": [1]},
            )
            assert score["ok"] is True
            assert score["data"]["result"]["brier_score"] == pytest.approx(0.04)
            invalid = await call(client, "compass_start", objective="")
            assert invalid["error"]["code"] == "INVALID_INPUT"
            for name in ("compass_get", "compass_review", "compass_brief"):
                missing = await call(client, name, decision_id="a" * 32)
                assert missing["error"]["code"] == "STORAGE_NOT_FOUND"
            missing = await call(client, "compass_list")
            assert missing["error"]["code"] == "STORAGE_NOT_FOUND"
        assert not path.parent.exists()

    anyio.run(scenario)


@sdk
def test_sdk_recovers_and_revises_a_decision_without_losing_history(tmp_path: Path) -> None:
    import anyio

    path = tmp_path / "decisions.sqlite3"

    async def scenario() -> None:
        async with session(path, tmp_path) as client:
            started = await call(client, "compass_start", objective="Choose a reversible pilot")
            decision_id = started["data"]["decision_id"]
            evidence = await call(
                client,
                "compass_record",
                decision_id=decision_id,
                expected_revision=1,
                kind="evidence",
                content="The synthetic pilot has capacity for ten users.",
                status="observed",
                source="synthetic capacity report v1",
            )
            prior_id = evidence["data"]["note_id"]
            recommendation = await call(
                client,
                "compass_record",
                decision_id=decision_id,
                expected_revision=2,
                kind="decision",
                content="Pilot if capacity remains above eight users.",
                depends_on=[prior_id],
            )
        async with session(path, tmp_path) as client:
            recovered = await call(client, "compass_list", limit=1, offset=0)
            assert recovered["data"]["total"] == 1
            assert recovered["data"]["decisions"][0]["decision_id"] == decision_id
            migrated = await call(client, "compass_migrate")
            assert migrated["data"]["migrated"] is False
            revision_arguments = {
                "decision_id": decision_id,
                "expected_revision": 3,
                "note_id": prior_id,
                "content": "The synthetic pilot has capacity for six users.",
                "reason": "A newer capacity measurement changed the operating envelope.",
                "status": "observed",
                "source": "synthetic capacity report v2",
            }
            revised = await call(client, "compass_revise", **revision_arguments)
            assert revised["data"]["revision"] == 4
            assert revised["data"]["supersedes"] == prior_id
            stale = await call(client, "compass_revise", **revision_arguments)
            assert stale["error"]["code"] == "REVISION_CONFLICT"
            brief = (await call(client, "compass_brief", decision_id=decision_id))["data"]
            assert brief["revision"] == 4
            assert brief["evidence"][0]["source"] == "synthetic capacity report v2"
            assert recommendation["data"]["note_id"] in {
                note["id"] for note in brief["stale_notes"]
            }
            history = (await call(client, "compass_get", decision_id=decision_id))["data"]
            assert len(history["revisions"]) == 1
            assert len(history["notes"]) == 3
            assert any(note["id"] == prior_id and note["stale"] for note in history["notes"])

    anyio.run(scenario)


@sdk
def test_sdk_reports_filesystem_failure_as_structured_error(tmp_path: Path) -> None:
    import anyio

    parent = tmp_path / "blocked"
    parent.write_text("existing user data")

    async def scenario() -> None:
        async with session(parent / "decisions.sqlite3", tmp_path) as client:
            failed = await call(client, "compass_start", objective="A valid local objective")
            assert failed["error"]["code"] == "STORAGE_ERROR"
        assert parent.read_text() == "existing user data"

    anyio.run(scenario)


@sdk
def test_sdk_preserves_unrelated_sqlite_data(tmp_path: Path) -> None:
    import anyio

    path = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE unrelated (value TEXT)")
        database.execute("INSERT INTO unrelated VALUES ('keep me')")
    original = path.read_bytes()

    async def scenario() -> None:
        async with session(path, tmp_path) as client:
            for name, arguments in (
                ("compass_get", {"decision_id": "a" * 32}),
                ("compass_start", {"objective": "A valid local objective"}),
                ("compass_migrate", {}),
            ):
                failed = await call(client, name, **arguments)
                assert failed["error"]["code"] == "INVALID_STORAGE"
        assert path.read_bytes() == original

    anyio.run(scenario)

"""Real stdio transport checks: no model, network client, or mocked server.

Run explicitly with ``uv run --frozen --extra dev --extra mcp pytest
 tests/test_mcp_live.py``. Without the optional SDK these tests are skipped.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
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
    "compass_preview_updates",
    "compass_apply_updates",
    "compass_plan_experiment",
    "compass_experiment",
    "compass_experiments",
    "compass_preview_observation",
    "compass_apply_observation",
}


@asynccontextmanager
async def client(db: Path):
    # Consume the actual host configuration generator, not a parallel recipe.
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/configure_mcp.py"), "--db", str(db)],
        check=True,
        capture_output=True,
        text=True,
    )
    config = json.loads(process.stdout)["mcpServers"]["compass"]
    assert config["env"]["COMPASS_DB"] == str(db)
    parameters = StdioServerParameters(**config)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=20) as session:
            initialized = await session.initialize()
            assert initialized.server_info.name == "COMPASS-C"
            assert "no result grants action permission" in initialized.instructions
            assert {tool.name for tool in (await session.list_tools()).tools} == TOOLS
            yield session


async def call(session, tool, **arguments):
    response = await session.call_tool(tool, arguments)
    assert not response.is_error, response
    texts = [item.text for item in response.content if item.type == "text"]
    assert len(texts) == 1, response
    return json.loads(texts[0])


def test_stdio_read_calculate_and_invalid_start_do_not_create_storage(tmp_path):
    async def scenario():
        db = tmp_path / "missing" / "notebook.sqlite3"
        async with client(db) as session:
            assert not db.parent.exists()
            result = await call(
                session,
                "compass_calculate",
                kind="bundle",
                parameters={"test_accuracy": 0.95, "test_cost": 3, "gain": 100, "loss": 400},
            )
            assert result["ok"]
            assert result["data"]["result"]["pair_value"] == pytest.approx(20.25)
            assert result["data"]["action_permission"] == "not_granted"
            for tool in ("compass_get", "compass_review"):
                error = await call(session, tool, decision_id="a" * 32)
                assert not error["ok"]
                assert error["error"]["code"] == "STORAGE_NOT_FOUND"
                assert set(error["error"]) == {"code", "message"}
                assert "only the configured notebook" in error["error"]["message"]
                assert "remains unknown from this check" in error["error"]["message"]
                assert "does not grant retry permission" in error["error"]["message"]
            listed = await call(session, "compass_list")
            assert "remains unknown" in listed["error"]["message"]
            assert "original notebook" in listed["error"]["message"]
            error = await call(session, "compass_start", objective="")
            assert not error["ok"]
            assert error["error"]["code"] == "INVALID_INPUT"
            error = await call(
                session,
                "compass_calculate",
                kind="feedback",
                parameters={"a": True, "gain": 0.5, "delay": 1},
            )
            assert not error["ok"]
            assert not db.parent.exists()

    asyncio.run(scenario())


def test_stdio_notebook_lifecycle_and_restart(tmp_path):
    async def scenario():
        db = tmp_path / "notebook.sqlite3"
        async with client(db) as session:
            started = await call(
                session,
                "compass_start",
                objective="Choose an isolated integration pilot",
                constraints=["Synthetic dogfood only; no external action"],
            )
            assert started["ok"]
            did = started["data"]["decision_id"]
            assert started["data"]["revision"] == 1
            note = await call(
                session,
                "compass_record",
                decision_id=did,
                expected_revision=1,
                kind="assumption",
                content="SDK and host support the stdio protocol",
                status="assumed",
            )
            nid = note["data"]["note_id"]
            conflict = await call(
                session,
                "compass_record",
                decision_id=did,
                expected_revision=1,
                kind="test",
                content="Stale write must not be appended",
            )
            assert conflict["error"]["code"] == "REVISION_CONFLICT"
            decision = await call(
                session,
                "compass_record",
                decision_id=did,
                expected_revision=2,
                kind="decision",
                content="Use the pilot conditionally",
                status="inferred",
                depends_on=[nid],
            )
            invalidated = await call(
                session,
                "compass_invalidate",
                decision_id=did,
                expected_revision=3,
                note_id=nid,
                reason="Host compatibility assumption withdrawn",
            )
            assert set(invalidated["data"]["invalidated"]) == {
                nid,
                decision["data"]["note_id"],
            }
            review = await call(session, "compass_review", decision_id=did)
            assert review["data"]["action_permission"] == "not_granted"
            assert not review["data"]["source_verified"]
        # A new process must read the same record, not an in-process singleton.
        async with client(db) as session:
            persisted = (await call(session, "compass_get", decision_id=did))["data"]
            assert persisted["revision"] == 4
            assert len(persisted["notes"]) == 2
            assert len(persisted["invalidations"]) == 1
            assert persisted["action_permission"] == "not_granted"

    asyncio.run(scenario())


@pytest.mark.parametrize("tool", ["compass_record", "compass_invalidate"])
@pytest.mark.parametrize("revision", [True, "1", 1.0])
def test_stdio_revision_type_is_not_coerced(tmp_path, revision, tool):
    async def scenario():
        async with client(tmp_path / "notebook.sqlite3") as session:
            started = await call(session, "compass_start", objective="No coerced revisions")
            did = started["data"]["decision_id"]
            arguments = {"decision_id": did, "expected_revision": revision}
            if tool == "compass_record":
                arguments.update(kind="test", content="Must not be recorded")
            else:
                note = await call(
                    session,
                    "compass_record",
                    decision_id=did,
                    expected_revision=1,
                    kind="assumption",
                    content="Must remain valid",
                    status="assumed",
                )
                arguments.update(note_id=note["data"]["note_id"], reason="Must not invalidate")
            before = (await call(session, "compass_get", decision_id=did))["data"]
            response = await session.call_tool(tool, arguments)
            assert response.is_error, response
            after = (await call(session, "compass_get", decision_id=did))["data"]
            assert after == before

    asyncio.run(scenario())

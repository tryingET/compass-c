"""Fresh-process acceptance of a persisted, explicitly observed experiment."""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from test_cli_journey import invoke as cli_invoke
from test_horizon_interfaces import EXPERIMENT, MODEL
from test_mcp_integration import call, session

SURFACES = [
    "package",
    "portable",
    pytest.param(
        "mcp",
        marks=pytest.mark.skipif(
            importlib.util.find_spec("mcp") is None, reason="requires the mcp extra"
        ),
    ),
]
PARAMETERS = {
    "model": MODEL,
    "experiments": [EXPERIMENT],
    "budget": 1,
    "max_duration": 20,
    "duration_unit": "minutes",
}
OBSERVATION = {
    "outcome": "pass",
    "source": "fixture://synthetic-check-result",
    "observed_at": "2026-09-08T01:00:00Z",
    "note": "Synthetic acceptance observation; not measured host benefit.",
}
HEAVY_FIELDS = {"parameters", "proposal", "current_model", "observation", "update"}


@asynccontextmanager
async def lifecycle_interface(surface: str, db: Path):
    if surface == "mcp":
        async with session(db, db.parent) as client:

            async def invoke(operation: str, **arguments: Any) -> dict[str, Any]:
                return await call(client, "compass_" + operation, **arguments)

            yield invoke
    else:

        async def invoke(operation: str, **arguments: Any) -> dict[str, Any]:
            args = [operation.replace("_", "-")]
            if operation in {"preview_observation", "apply_observation"}:
                args = ["observe-experiment"]
                if operation == "apply_observation":
                    args.append("--apply")
            for key in ("decision_id", "plan_id"):
                if key in arguments:
                    args.append(arguments.pop(key))
            for key, value in arguments.items():
                flag = {
                    "expected_revision": "revision",
                    "experiment_id": "experiment",
                }.get(key, key.replace("_", "-"))
                if key in {"parameters", "observation"}:
                    path = db.parent / (key + ".json")
                    path.write_text(json.dumps(value), encoding="utf-8")
                    args += ["--" + flag + "-file", str(path)]
                elif key == "full":
                    if value:
                        args.append("--full")
                else:
                    args += [
                        "--" + flag,
                        json.dumps(value) if isinstance(value, (dict, list)) else str(value),
                    ]
            code, payload = cli_invoke(db, *args, portable=surface == "portable")
            assert code == (0 if payload["ok"] else 2), payload
            return payload

        yield invoke


def successful(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload["ok"], payload
    assert payload["data"]["action_permission"] == "not_granted"
    return payload["data"]


def compact(payload: dict[str, Any]) -> None:
    assert not (HEAVY_FIELDS & payload.keys())
    assert payload["summary"]["next_action"]
    assert payload["source_verified"] is False


@pytest.mark.parametrize("surface", SURFACES)
def test_saved_plan_resumes_and_observes_once_through_a_new_client(tmp_path, surface):
    db = tmp_path / "decision.sqlite3"

    async def scenario():
        async with lifecycle_interface(surface, db) as invoke:
            started = successful(await invoke("start", objective="Choose a bounded release"))
            did = started["decision_id"]
            saved = successful(
                await invoke(
                    "plan_experiment",
                    decision_id=did,
                    expected_revision=1,
                    parameters=PARAMETERS,
                )
            )
            compact(saved)
            assert saved["revision"] == 2
            assert saved["status"] == "awaiting_observation"
            assert saved["summary"]["current_winners"] == ["defer"]
            plan_id = saved["plan_id"]
            recommendation = successful(
                await invoke(
                    "record",
                    decision_id=did,
                    expected_revision=2,
                    kind="decision",
                    content="Defer until the bounded check supplies evidence",
                    depends_on=[saved["model_note_id"]],
                )
            )

        async with lifecycle_interface(surface, db) as invoke:
            listed = successful(await invoke("experiments", decision_id=did))
            assert listed["experiments"][0]["plan_id"] == plan_id
            assert not (HEAVY_FIELDS & listed["experiments"][0].keys())
            resumed = successful(await invoke("experiment", plan_id=plan_id))
            compact(resumed)
            assert resumed["revision"] == 3
            assert resumed["plan_revision"] == 2
            full = successful(await invoke("experiment", plan_id=plan_id, full=True))
            assert full["parameters"] == PARAMETERS
            assert full["current_model"]["probabilities"] == [0.5, 0.5]
            assert full["proposal"]["result"]["proposed_experiment_ids"] == ["check"]
            observation_args = {
                "plan_id": plan_id,
                "expected_revision": 3,
                "experiment_id": "check",
                "event_id": "acceptance-event-1",
                "observation": OBSERVATION,
            }
            before = db.read_bytes()
            preview = successful(await invoke("preview_observation", **observation_args))
            compact(preview)
            assert preview["revision"] == 3
            assert preview["applied"] is False
            assert preview["summary"]["posterior_winners"] == ["ship"]
            assert recommendation["note_id"] in preview["invalidated"]
            assert db.read_bytes() == before
            applied = successful(await invoke("apply_observation", **observation_args, full=True))
            assert applied["applied"] is True
            assert applied["revision"] == 4
            assert applied["update"]["result"]["model"]["probabilities_exact"] == [
                "4/5",
                "1/5",
            ]
            assert applied["update"]["result"]["prior_model"] == MODEL
            after = db.read_bytes()
            replayed = successful(await invoke("apply_observation", **observation_args))
            compact(replayed)
            assert replayed["replayed"] is True
            assert replayed["applied"] is False
            assert replayed["revision"] == 4
            assert db.read_bytes() == after
            conflict_args = copy.deepcopy(observation_args)
            conflict_args["observation"]["outcome"] = "fail"
            conflict = await invoke("apply_observation", **conflict_args)
            assert conflict["error"]["code"] == "OBSERVATION_CONFLICT"
            assert db.read_bytes() == after
            brief = successful(await invoke("brief", decision_id=did))
            assert brief["recommendations"] == []
            assert recommendation["note_id"] in {note["id"] for note in brief["stale_notes"]}
            assert brief["experiments"][0]["plan_id"] == plan_id
            assert brief["experiments"][0]["revision"] == brief["revision"] == 4
            assert brief["experiments"][0]["summary"]["current_winners"] == ["ship"]
            assert not (HEAVY_FIELDS & brief["experiments"][0].keys())

        async with lifecycle_interface(surface, db) as invoke:
            observed = successful(await invoke("experiment", plan_id=plan_id, full=True))
            assert observed["status"] == "observed"
            assert observed["parameters"] == PARAMETERS
            assert observed["current_model"]["probabilities_exact"] == ["4/5", "1/5"]
            assert observed["observation"]["event_id"] == "acceptance-event-1"

    asyncio.run(scenario())


@pytest.mark.parametrize("portable", [False, True], ids=["package", "portable"])
@pytest.mark.parametrize(
    "raw,code",
    [
        (None, "INPUT_FILE_ERROR"),
        (b"\xff", "INPUT_FILE_ERROR"),
        ("{", "INVALID_JSON"),
        ('{"model": {}, "model": {}}', "INVALID_JSON"),
        ('{"cost": NaN}', "INVALID_JSON"),
        (" " * 1_000_001, "INPUT_TOO_LARGE"),
    ],
    ids=["missing", "invalid-utf8", "malformed", "duplicate-key", "nonfinite", "oversized"],
)
@pytest.mark.parametrize("command", ["plan-experiment", "observe-experiment"])
def test_lifecycle_file_errors_are_structured_and_do_not_create_storage(
    tmp_path, portable, raw, code, command
):
    db = tmp_path / "absent.sqlite3"
    path = tmp_path / "input.json"
    if isinstance(raw, bytes):
        path.write_bytes(raw)
    elif raw is not None:
        path.write_text(raw, encoding="utf-8")
    args = [command, "a" * 32, "--revision", "1"]
    if command == "plan-experiment":
        args += ["--parameters-file", str(path)]
    else:
        args += ["--experiment", "check", "--event-id", "event-1", "--observation-file", str(path)]
    exit_code, payload = cli_invoke(db, *args, portable=portable)
    assert exit_code == 2
    assert payload["error"]["code"] == code
    assert not db.exists()


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="requires the mcp extra")
def test_mcp_lifecycle_rejects_revision_coercion_before_creating_storage(tmp_path):
    db = tmp_path / "absent.sqlite3"

    async def scenario():
        async with session(db, tmp_path) as client:
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assert {
                "compass_plan_experiment",
                "compass_preview_observation",
                "compass_apply_observation",
            } <= tools
            for revision in (True, 1.0, "1"):
                for operation in ("plan_experiment", "preview_observation", "apply_observation"):
                    arguments = (
                        {"decision_id": "a" * 32, "parameters": PARAMETERS}
                        if operation == "plan_experiment"
                        else {
                            "plan_id": "a" * 32,
                            "experiment_id": "check",
                            "event_id": "event-1",
                            "observation": OBSERVATION,
                        }
                    )
                    response = await client.call_tool(
                        "compass_" + operation, {**arguments, "expected_revision": revision}
                    )
                    assert response.is_error or response.structured_content["ok"] is False
        assert not db.exists()

    asyncio.run(scenario())


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="requires the mcp extra")
def test_mcp_full_output_option_requires_an_actual_boolean(tmp_path):
    db = tmp_path / "absent.sqlite3"

    async def scenario():
        async with session(db, tmp_path) as client:
            assert "compass_experiment" in {tool.name for tool in (await client.list_tools()).tools}
            for full in ("false", "true", 0, 1):
                response = await client.call_tool(
                    "compass_experiment", {"plan_id": "a" * 32, "full": full}
                )
                assert response.is_error
        assert not db.exists()

    asyncio.run(scenario())

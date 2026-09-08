"""Real interface journeys for portfolio, experiments and explicit evidence updates."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from contextlib import asynccontextmanager

import pytest
from test_cli_journey import success
from test_mcp_integration import call, session

PORTFOLIO = {
    "stakeholders": ["operator", "maintainer"],
    "resources": {"hours": 2},
    "decisions": [
        {
            "id": "extend",
            "resources": {"hours": 2},
            "values": {"operator": 5, "maintainer": 1},
            "defer_values": {"operator": 1, "maintainer": 4},
        }
    ],
}
MODEL = {
    "actions": ["ship", "defer"],
    "scenarios": ["ready", "not ready"],
    "payoffs": [[10, -20], [0, 0]],
    "probabilities": [0.5, 0.5],
    "value_unit": "illustrative utility points",
    "provenance": ["Synthetic interface acceptance fixture"],
    "assumptions": ["Illustrative finite model; not an empirical probability estimate"],
}
EXPERIMENT = {
    "id": "check",
    "question": "Does the bounded check pass?",
    "protocol": "Observe one declared pass/fail result; no command is executed by the model.",
    "outcomes": ["pass", "fail"],
    "likelihoods": [[0.8, 0.2], [0.2, 0.8]],
    "cost": 0.5,
    "duration": 10,
    "provenance": ["Synthetic interface acceptance fixture"],
    "assumptions": ["Hypothetical exhaustive observation likelihoods"],
}


@asynccontextmanager
async def interface(surface, db):
    if surface == "mcp":
        async with session(db, db.parent) as client:

            async def invoke(operation, **parameters):
                response = await call(client, "compass_" + operation, **parameters)
                assert response["ok"], response
                return response["data"]

            yield invoke
    else:

        async def invoke(operation, **parameters):
            args = []
            if operation in {"preview_updates", "apply_updates"}:
                args = ["update-evidence", parameters.pop("decision_id")]
                if operation == "apply_updates":
                    args.append("--apply")
            elif operation == "calculate":
                args = [operation, parameters.pop("kind")]
            else:
                args = [operation]
                if "decision_id" in parameters:
                    args.append(parameters.pop("decision_id"))
            for key, value in parameters.items():
                flag = "revision" if key == "expected_revision" else key.replace("_", "-")
                args += [
                    "--" + flag,
                    json.dumps(value) if isinstance(value, (dict, list)) else str(value),
                ]
            return success(db, *args, portable=surface == "portable")

        yield invoke


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


@pytest.mark.parametrize("surface", SURFACES)
def test_full_horizon_calculations_are_transient_and_preserve_boundaries(tmp_path, surface):
    db = tmp_path / "absent.sqlite3"

    async def scenario():
        async with interface(surface, db) as invoke:
            portfolio = await invoke("calculate", kind="portfolio", parameters=PORTFOLIO)
            assert portfolio["result"]["preference_conflict"] is True
            assert portfolio["result"]["common_optima"] == []
            assert portfolio["action_permission"] == "not_granted"
            proposal = await invoke(
                "calculate",
                kind="experiment",
                parameters={
                    "model": MODEL,
                    "experiments": [EXPERIMENT],
                    "budget": 1,
                    "max_duration": 20,
                    "duration_unit": "minutes",
                },
            )
            assert proposal["result"]["baseline"]["expected_value_winners"] == ["defer"]
            assert proposal["result"]["proposed_experiment_ids"] == ["check"]
            assert proposal["action_permission"] == "not_granted"
            revised = await invoke(
                "calculate",
                kind="update_beliefs",
                parameters={
                    "model": MODEL,
                    "experiment": EXPERIMENT,
                    "observation": {
                        "outcome": "pass",
                        "source": "synthetic acceptance observation",
                        "observed_at": "2026-09-08T01:00:00Z",
                        "note": "Fixture result, not real deployment evidence",
                    },
                },
            )
            assert revised["result"]["updated_model"]["probabilities"] == [0.8, 0.2]
            assert revised["action_permission"] == "not_granted"
        assert not db.exists()

    asyncio.run(scenario())


@pytest.mark.parametrize("surface", SURFACES)
def test_evidence_preview_and_explicit_apply_preserve_history(tmp_path, surface):
    db = tmp_path / "decision.sqlite3"

    async def scenario():
        async with interface(surface, db) as invoke:
            state = await invoke("start", objective="Choose whether to retain the candidate")
            did = state["decision_id"]
            evidence = await invoke(
                "record",
                decision_id=did,
                expected_revision=state["revision"],
                kind="evidence",
                content="Candidate has not passed isolated verification",
                status="observed",
                source="fixture baseline",
            )
            decision = await invoke(
                "record",
                decision_id=did,
                expected_revision=evidence["revision"],
                kind="decision",
                content="Hold the candidate pending verification",
                depends_on=[evidence["note_id"]],
            )
            parameters = {
                "decision_id": did,
                "expected_revision": decision["revision"],
                "updates": [
                    {
                        "note_id": evidence["note_id"],
                        "content": "Candidate passed isolated verification",
                        "reason": "New explicit check result",
                        "status": "observed",
                        "source": "fixture corrected observation",
                    }
                ],
            }
            preview = await invoke("preview_updates", **parameters)
            assert preview["applied"] is False
            assert decision["note_id"] in preview["invalidated"]
            before = await invoke("get", decision_id=did)
            assert before["revision"] == decision["revision"]
            applied = await invoke("apply_updates", **parameters)
            assert applied["applied"] is True
            assert applied["revision"] == decision["revision"] + 1
            assert applied["source_verified"] is False
            brief = await invoke("brief", decision_id=did)
            assert brief["recommendations"] == []
            assert brief["evidence"][0]["source"] == "fixture corrected observation"
            assert {evidence["note_id"], decision["note_id"]} <= {
                note["id"] for note in brief["stale_notes"]
            }

    asyncio.run(scenario())

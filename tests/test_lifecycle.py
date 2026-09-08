"""Executable BDD scenarios for features/experiment_lifecycle.feature."""

from __future__ import annotations

import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from compass_c import CompassError, Notebook
from compass_c.experiments import propose_experiments, revise_model
from compass_c.lifecycle import (
    apply_observation,
    experiment,
    experiments,
    plan_experiment,
    preview_observation,
)


def parameters():
    return {
        "model": {
            "actions": ["ship", "defer"],
            "scenarios": ["ready", "not ready"],
            "payoffs": [[10, -20], [0, 0]],
            "probabilities": [0.5, 0.5],
            "value_unit": "illustrative utility points",
            "provenance": ["Author-visible synthetic fixture; not measured usefulness."],
            "assumptions": ["The two scenarios exhaust the supplied model."],
        },
        "experiments": [{
            "id": "smoke",
            "question": "Does the isolated installation pass?",
            "protocol": "Run one isolated installation and capture the result.",
            "outcomes": ["pass", "fail"],
            "likelihoods": [[0.8, 0.2], [0.2, 0.8]],
            "cost": 0.5,
            "duration": 10,
            "provenance": ["Explicit synthetic likelihoods; no calibration claim."],
            "assumptions": ["One mutually exclusive outcome."],
        }],
        "budget": 1,
        "max_duration": 20,
        "duration_unit": "minutes",
    }


def observation(**overrides):
    return {
        "outcome": "pass",
        "source": "fixture://installation/pass",
        "observed_at": "2026-09-08T01:00:00Z",
        "note": "Synthetic fixture result; not an actual installation claim.",
        **overrides,
    }


@pytest.fixture
def saved(tmp_path: Path):
    book = Notebook(tmp_path / "experiment.sqlite3")
    did = book.start("Choose the next bounded development experiment")["decision_id"]
    evidence = book.record(did, 1, "evidence", "Initial state", "observed", "fixture://prior")
    plan = plan_experiment(book, did, evidence["revision"], parameters(), [evidence["note_id"]])
    return book, did, evidence["note_id"], plan


def assert_boundary(result):
    assert result["action_permission"] == "not_granted"
    assert result["scope"] == "analysis_only"
    assert result["source_verified"] is False


def test_freeze_resume_and_list_preserve_inputs_without_read_side_effects(saved):
    book, did, evidence_id, plan = saved
    frozen = parameters()
    assert plan["parameters"] == frozen
    assert plan["proposal"] == propose_experiments(frozen)
    assert plan["status"] == "awaiting_observation"
    assert plan["plan_revision"] == plan["revision"] == 3
    assert plan["summary"]["current_winners"] == ["defer"]
    assert plan["summary"]["proposed_experiment_ids"] == ["smoke"]
    assert plan["summary"]["next_action"]
    snapshot = book.get(did)
    anchor = next(n for n in snapshot["notes"] if n["id"] == plan["model_note_id"])
    assert anchor["kind"] == "forecast"
    assert anchor["depends_on"] == [evidence_id]
    before = book.path.read_bytes()
    resumed = experiment(Notebook(book.path), plan["plan_id"])
    assert resumed == plan
    listed = experiments(book, did)
    assert listed["experiments"][0]["plan_id"] == plan["plan_id"]
    assert listed["experiments"][0]["status"] == "awaiting_observation"
    assert book.path.read_bytes() == before
    assert_boundary(resumed)
    assert_boundary(listed)


def test_caller_mutation_cannot_rewrite_frozen_plan(tmp_path):
    book = Notebook(tmp_path / "frozen.sqlite3")
    did = book.start("Freeze the supplied assumptions")["decision_id"]
    supplied = parameters()
    original = copy.deepcopy(supplied)
    plan = plan_experiment(book, did, 1, supplied)
    supplied["model"]["probabilities"][0] = 1
    plan["parameters"]["model"]["actions"].append("invented")
    assert experiment(book, plan["plan_id"])["parameters"] == original


def test_preview_and_atomic_apply_retain_posterior_and_invalidate_reasoning(saved):
    book, did, _, plan = saved
    recommendation = book.record(
        did, 3, "decision", "Defer until the experiment resolves uncertainty",
        depends_on=[plan["model_note_id"]],
    )
    before = book.get(did)
    before_bytes = book.path.read_bytes()
    result = preview_observation(book, plan["plan_id"], 4, "smoke", "event-1", observation())
    assert result["applied"] is False
    assert result["replayed"] is False
    assert result["revision"] == 4
    expected = revise_model({
        "model": parameters()["model"],
        "experiment": parameters()["experiments"][0],
        "observation": observation(),
    })
    assert result["update"] == expected
    assert set(result["invalidated"]) == {plan["model_note_id"], recommendation["note_id"]}
    assert book.get(did) == before
    assert book.path.read_bytes() == before_bytes
    applied = apply_observation(book, plan["plan_id"], 4, "smoke", "event-1", observation())
    assert applied["applied"] is True
    assert applied["revision"] == 5
    assert applied["update"] == expected
    after = book.get(did)
    assert after["revision"] == 5
    assert len(after["notes"]) == len(before["notes"]) + 2
    assert len(after["revisions"]) == len(after["invalidations"]) == 1
    notes = {n["id"]: n for n in after["notes"]}
    assert notes[applied["outcome_note_id"]]["source"] == observation()["source"]
    assert notes[applied["outcome_note_id"]]["status"] == "observed"
    assert notes[applied["model_note_id"]]["kind"] == "forecast"
    assert notes[applied["model_note_id"]]["stale"] is False
    assert notes[plan["model_note_id"]]["stale"] is True
    assert notes[recommendation["note_id"]]["stale"] is True
    assert after["revisions"][0]["supersedes"] == plan["model_note_id"]
    assert book.brief(did)["recommendations"] == []
    resumed = experiment(book, plan["plan_id"])
    assert resumed["status"] == "observed"
    assert resumed["current_model"]["probabilities_exact"] == ["4/5", "1/5"]
    assert resumed["summary"]["current_winners"] == ["ship"]
    assert resumed["parameters"] == parameters()
    assert resumed["observation"]["event_id"] == "event-1"
    assert_boundary(result)
    assert_boundary(applied)


def test_retry_returns_original_receipt_before_revision_check_without_double_count(saved):
    book, did, _, plan = saved
    first = apply_observation(book, plan["plan_id"], 3, "smoke", "event-1", observation())
    book.record(did, 4, "limitation", "No host usefulness inference")
    before = book.path.read_bytes()
    for operation in (preview_observation, apply_observation):
        retry = operation(book, plan["plan_id"], 3, "smoke", "event-1", observation())
        assert retry["replayed"] is True
        assert retry["applied"] is False
        assert retry["revision"] == first["revision"] == 4
        assert retry["current_revision"] == 5
        assert retry["update"] == first["update"]
        assert book.path.read_bytes() == before


@pytest.mark.parametrize("operation", [preview_observation, apply_observation])
@pytest.mark.parametrize("case,code", [
    ("different_payload", "OBSERVATION_CONFLICT"),
    ("different_event", "EXPERIMENT_COMPLETE"),
    ("different_plan", "OBSERVATION_CONFLICT"),
])
def test_duplicate_event_and_completed_plan_errors_are_atomic(saved, operation, case, code):
    book, did, _, plan = saved
    apply_observation(book, plan["plan_id"], 3, "smoke", "event-1", observation())
    target, event, observed = plan["plan_id"], "event-1", observation()
    if case == "different_payload":
        observed["note"] = "A changed assertion using the same event identity"
    elif case == "different_event":
        event = "event-2"
    else:
        target = plan_experiment(book, did, 4, parameters())["plan_id"]
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        operation(book, target, book.get(did)["revision"], "smoke", event, observed)
    assert error.value.code == code
    assert book.path.read_bytes() == before


def test_event_identity_is_scoped_to_decision(saved):
    book, _, _, plan = saved
    apply_observation(book, plan["plan_id"], 3, "smoke", "event-1", observation())
    other = book.start("Another decision legitimately uses the same observation")["decision_id"]
    second = plan_experiment(book, other, 1, parameters())
    assert apply_observation(book, second["plan_id"], 2, "smoke", "event-1", observation())["applied"]


def test_evidence_revision_requires_replanning(saved):
    book, did, evidence, plan = saved
    book.revise(did, 3, evidence, "Changed initial state", "New evidence", "observed", "fixture://new")
    assert experiment(book, plan["plan_id"])["status"] == "needs_replan"
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        apply_observation(book, plan["plan_id"], 4, "smoke", "event-1", observation())
    assert error.value.code == "STALE_DEPENDENCY"
    assert book.path.read_bytes() == before


@pytest.mark.parametrize("case,code", [
    ("revision", "REVISION_CONFLICT"),
    ("experiment", "INVALID_INPUT"),
    ("event", "INVALID_INPUT"),
    ("observation", "INVALID_INPUT"),
    ("timestamp", "INVALID_INPUT"),
    ("unknown_field", "INVALID_INPUT"),
])
def test_invalid_observation_is_atomic(saved, case, code):
    book, _, _, plan = saved
    rev, candidate, event, observed = 3, "smoke", "event-1", observation()
    if case == "revision":
        rev = 2
    elif case == "experiment":
        candidate = "unknown"
    elif case == "event":
        event = " "
    elif case == "observation":
        observed["source"] = ""
    elif case == "timestamp":
        observed["observed_at"] = "2026-09-08"
    else:
        observed["fetch_source"] = True
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        apply_observation(book, plan["plan_id"], rev, candidate, event, observed)
    assert error.value.code == code
    assert book.path.read_bytes() == before


def test_impossible_observation_retains_prior_without_partial_rows(tmp_path):
    book = Notebook(tmp_path / "impossible.sqlite3")
    did = book.start("Inspect an impossible model result")["decision_id"]
    supplied = parameters()
    supplied["experiments"][0]["outcomes"].append("impossible")
    for row in supplied["experiments"][0]["likelihoods"]:
        row.append(0)
    plan = plan_experiment(book, did, 1, supplied)
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        apply_observation(book, plan["plan_id"], 2, "smoke", "event-1", observation(outcome="impossible"))
    assert error.value.code == "IMPOSSIBLE_OBSERVATION"
    assert book.path.read_bytes() == before
    assert experiment(book, plan["plan_id"])["observation"] is None


def test_no_informative_candidate_is_saved_without_an_invented_experiment(tmp_path):
    book = Notebook(tmp_path / "no-test.sqlite3")
    did = book.start("Do not spend for irrelevant information")["decision_id"]
    supplied = parameters()
    supplied["experiments"] = []
    plan = plan_experiment(book, did, 1, supplied)
    assert plan["status"] == "no_informative_experiment"
    assert plan["summary"]["proposed_experiment_ids"] == []
    assert plan["summary"]["current_winners"] == ["defer"]
    assert plan["summary"]["next_action"]


def test_observation_refuses_experiment_outside_frozen_bounds(tmp_path):
    book = Notebook(tmp_path / "bounds.sqlite3")
    did = book.start("Retain explicit experiment bounds")["decision_id"]
    supplied = parameters()
    supplied["budget"] = 0
    plan = plan_experiment(book, did, 1, supplied)
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        apply_observation(book, plan["plan_id"], 2, "smoke", "event-1", observation())
    assert error.value.code == "EXPERIMENT_NOT_ELIGIBLE"
    assert book.path.read_bytes() == before


@pytest.mark.parametrize("dependencies,code", [
    (["f" * 32], "INVALID_DEPENDENCY"),
    (["invalid"], "INVALID_INPUT"),
])
def test_invalid_plan_dependency_is_atomic(saved, dependencies, code):
    book, did, _, _ = saved
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        plan_experiment(book, did, 3, parameters(), dependencies)
    assert error.value.code == code
    assert book.path.read_bytes() == before


@pytest.mark.parametrize("column,value", [
    ("parameters_json", "{"),
    ("proposal_json", "{}"),
    ("revision", 999),
    ("model_note_id", "f" * 32),
])
def test_malformed_saved_plan_fails_closed(saved, column, value):
    book, _, _, plan = saved
    with sqlite3.connect(book.path) as db:
        db.execute(f"UPDATE experiment_plans SET {column}=? WHERE id=?", (value, plan["plan_id"]))
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        experiment(book, plan["plan_id"])
    assert error.value.code == "INVALID_STORAGE"
    assert book.path.read_bytes() == before


def test_contradictory_saved_posterior_fails_closed(saved):
    book, _, _, plan = saved
    apply_observation(book, plan["plan_id"], 3, "smoke", "event-1", observation())
    with sqlite3.connect(book.path) as db:
        update = json.loads(db.execute("SELECT update_json FROM experiment_observations").fetchone()[0])
        update["result"]["model"]["probabilities"] = [1, 0]
        db.execute("UPDATE experiment_observations SET update_json=?", (json.dumps(update),))
    with pytest.raises(CompassError) as error:
        experiment(book, plan["plan_id"])
    assert error.value.code == "INVALID_STORAGE"


def test_concurrent_identical_event_is_applied_once(saved):
    book, did, _, plan = saved
    barrier = Barrier(2)

    def apply():
        barrier.wait(timeout=10)
        return apply_observation(Notebook(book.path), plan["plan_id"], 3, "smoke", "event-1", observation())

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: apply(), range(2)))
    assert sorted(r["replayed"] for r in receipts) == [False, True]
    assert book.get(did)["revision"] == 4
    with sqlite3.connect(book.path) as db:
        assert db.execute("SELECT COUNT(*) FROM experiment_observations").fetchone()[0] == 1


def test_read_and_failed_plan_do_not_create_storage(tmp_path):
    book = Notebook(tmp_path / "absent.sqlite3")
    for operation in (
        lambda: experiment(book, "f" * 32),
        lambda: experiments(book, "f" * 32),
        lambda: plan_experiment(book, "f" * 32, 1, parameters()),
    ):
        with pytest.raises(CompassError) as error:
            operation()
        assert error.value.code == "STORAGE_NOT_FOUND"
        assert not book.path.exists()

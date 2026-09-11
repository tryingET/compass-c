"""Explicit, resumable single-observation experiments in a local decision notebook.

Frozen models and protocols are advisory. Sources are retained without being read;
event identities prevent repeated incorporation of the same declared event, not
semantic duplication hidden behind different identifiers.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import uuid
from typing import Any

from .core import CompassError, Notebook, identifier, integer, strings, text, utc
from .experiments import propose_experiments, revise_model

_PAYLOAD_LIMIT = 1_000_000
_PLAN_LIMIT = 128
_BOUNDARY = {
    "scope": "analysis_only",
    "action_permission": "not_granted",
    "source_verified": False,
}


def lifecycle_view(payload: dict[str, Any], full: bool = False) -> dict[str, Any]:
    """Share the same concise, source-faithful view across all client adapters."""
    omitted = (
        set() if full else {"parameters", "proposal", "current_model", "observation", "update"}
    )
    return copy.deepcopy({key: value for key, value in payload.items() if key not in omitted})


def _encode(value: Any, field: str) -> str:
    try:
        encoded = json.dumps(
            value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        encoded.encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise CompassError("INVALID_INPUT", f"{field} must be finite UTF-8 JSON") from exc
    if len(encoded) > _PAYLOAD_LIMIT:
        raise CompassError("INPUT_TOO_LARGE", f"{field} exceeds the retained payload limit")
    return encoded


def _decode(raw: Any, field: str) -> Any:
    text(raw, field, limit=_PAYLOAD_LIMIT)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate stored key")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("Non-finite stored value")

    decoded = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    _encode(decoded, field)
    return decoded


def _require_schema(book: Notebook, database: sqlite3.Connection) -> None:
    if book._verify_schema(database) != "3":
        raise CompassError(
            "MIGRATION_REQUIRED", "Run migrate explicitly before using experiment lifecycle storage"
        )


def _dependencies(snapshot: dict, depends_on: Any) -> list[str]:
    dependencies = strings([] if depends_on is None else depends_on, "depends_on")
    if len(dependencies) > 63:
        raise CompassError(
            "CAPACITY", "An experiment reserves one dependency link for its observed outcome"
        )
    if len(dependencies) != len(set(dependencies)):
        raise CompassError("INVALID_INPUT", "Duplicate dependencies")
    notes = {note["id"]: note for note in snapshot["notes"]}
    for dependency in dependencies:
        identifier(dependency, "dependency")
        if dependency not in notes:
            raise CompassError("INVALID_DEPENDENCY", "Dependency belongs elsewhere")
        if notes[dependency]["stale"]:
            raise CompassError("STALE_DEPENDENCY", "Cannot build on invalidated evidence")
    return dependencies


def _candidate(proposal: dict, candidate_id: str) -> dict:
    text(candidate_id, "experiment_id", limit=2_000)
    candidates = {candidate["id"]: candidate for candidate in proposal["result"]["experiments"]}
    if candidate_id not in candidates:
        raise CompassError("INVALID_INPUT", "Experiment is not part of the frozen plan")
    candidate = candidates[candidate_id]
    if not candidate["within_budget"] or not candidate["within_duration"]:
        raise CompassError(
            "EXPERIMENT_NOT_ELIGIBLE", "Experiment exceeds the frozen cost or duration bound"
        )
    return candidate["experiment"]


def _observation(value: Any) -> dict:
    if type(value) is not dict:
        raise CompassError("INVALID_INPUT", "observation must be an object")
    # The calculation checks the exact field set and timestamp. Notebook sources
    # have a smaller bound than transient calculation strings.
    if "source" in value:
        text(value["source"], "source", limit=4_000)
    return json.loads(_encode(value, "observation"))


def _plan_summary(plan: dict) -> dict:
    proposal = plan["proposal"]["result"]
    receipt = plan["observation"]
    if receipt is not None:
        winners = receipt["update"]["result"]["posterior_winners"]
        next_action = (
            "Reconsider invalidated recommendations using the retained posterior. "
            "For another observation, freeze a new plan with likelihoods "
            "conditional on this evidence."
        )
    else:
        winners = proposal["baseline"]["expected_value_winners"]
        next_action = {
            "needs_replan": (
                "The model depends on stale evidence. Review changed evidence "
                "and freeze a new plan before using another result."
            ),
            "no_informative_experiment": (
                "No positive-net-value experiment is proposed within the supplied bounds. "
                "Inspect the no-test option or explicitly revise the model."
            ),
            "awaiting_observation": (
                "Inspect the proposed protocol and its bounds. If the owner obtains an actual "
                "result, preview it with a stable event identity before applying it."
            ),
        }[plan["status"]]
    recorded_winners = winners
    if plan["current_model_stale"]:
        winners = []
        next_action = (
            "The recorded model depends on changed evidence. Preserve this history and "
            "freeze a new plan after reviewing the changed evidence and conditional likelihoods."
        )
    candidates = []
    for row in proposal["experiments"]:
        candidate = row["experiment"]
        candidates.append(
            {
                "id": row["id"],
                "question": candidate["question"],
                "protocol": candidate["protocol"],
                "cost": candidate["cost"],
                "duration": candidate["duration"],
                "status": row["status"],
                "net_information_value": row["net_information_value"],
                "net_information_value_exact": row["net_information_value_exact"],
                "outcomes": [
                    {
                        "outcome": branch["outcome"],
                        "probability_exact": branch["probability_exact"],
                        "possible": branch["possible"],
                        "expected_value_winners": branch["expected_value_winners"],
                        "preference_changed": branch["preference_changed"],
                    }
                    for branch in row["outcomes"]
                ],
            }
        )
    return {
        "current_winners": winners,
        "recorded_winners": recorded_winners,
        "proposed_experiment_ids": (
            proposal["proposed_experiment_ids"]
            if receipt is None and not plan["current_model_stale"]
            else []
        ),
        "proposal_basis": "frozen_prior",
        "proposal_current": receipt is None and not plan["current_model_stale"],
        "single_observation_consumed": receipt is not None,
        "no_test": proposal["baseline"],
        "candidates": candidates,
        "bounds": {key: proposal[key] for key in ("budget", "max_duration", "duration_unit")},
        "value_unit": plan["parameters"]["model"]["value_unit"],
        "next_action": next_action,
        "source_verified": False,
    }


def _update_summary(update: dict) -> dict:
    result = update["result"]
    return {
        "prior_winners": result["prior_winners"],
        "posterior_winners": result["posterior_winners"],
        "preference_changed": result["preference_changed"],
        "prior_winners_rejected": result["prior_winners_rejected"],
        "evidence_probability_exact": result["evidence_probability_exact"],
        "source": result["observation"]["source"],
        "observed_at": result["observation"]["observed_at"],
        "outcome": result["observation"]["outcome"],
        "next_action": (
            "Inspect the conditional change and affected notes. Reconsider recommendations "
            "explicitly; the result grants no action permission."
        ),
        "source_verified": False,
    }


def _load(book: Notebook, database: sqlite3.Connection, plan_id: str) -> tuple[dict, dict]:
    identifier(plan_id, "plan_id")
    _require_schema(book, database)
    row = database.execute("SELECT * FROM experiment_plans WHERE id=?", (plan_id,)).fetchone()
    if row is None:
        raise CompassError("NOT_FOUND", "Experiment plan not found")
    try:
        identifier(row["id"], "stored plan_id")
        identifier(row["decision_id"], "stored decision_id")
        identifier(row["model_note_id"], "stored model_note_id")
        text(row["created_at"], "stored created_at")
        snapshot = book._snapshot(database, row["decision_id"])
        integer(row["revision"], "stored plan revision", 2, snapshot["revision"])
        notes = {note["id"]: note for note in snapshot["notes"]}
        anchor = notes.get(row["model_note_id"])
        if anchor is None or (
            anchor["kind"] != "forecast"
            or anchor["status"] != "computed"
            or anchor["source"] != f"compass-c:experiment-plan:{plan_id}"
            or anchor["content"] != f"Frozen model for experiment plan {plan_id}."
            or anchor["created_at"] != row["created_at"]
        ):
            raise ValueError("Invalid model anchor")
        parameters = _decode(row["parameters_json"], "stored parameters")
        proposal = _decode(row["proposal_json"], "stored proposal")
        expected = propose_experiments(parameters)
        if proposal != expected:
            raise ValueError("Stored proposal contradicts frozen parameters")
        observed = database.execute(
            "SELECT * FROM experiment_observations WHERE plan_id=?", (plan_id,)
        ).fetchall()
        if len(observed) > 1:
            raise ValueError("Plan has multiple observations")
        receipt = None
        current_model = parameters["model"]
        current_model_note_id = anchor["id"]
        current_model_stale = anchor["stale"]
        if observed:
            event = observed[0]
            for key in ("id", "decision_id", "plan_id", "outcome_note_id", "model_note_id"):
                identifier(event[key], f"stored {key}")
            text(event["event_id"], "stored event_id", limit=200)
            text(event["created_at"], "stored created_at")
            integer(
                event["revision"],
                "stored observation revision",
                row["revision"] + 1,
                snapshot["revision"],
            )
            if event["decision_id"] != row["decision_id"]:
                raise ValueError("Observation belongs to another decision")
            if (
                database.execute(
                    "SELECT COUNT(*) FROM experiment_observations "
                    "WHERE decision_id=? AND event_id=?",
                    (row["decision_id"], event["event_id"]),
                ).fetchone()[0]
                != 1
            ):
                raise ValueError("Duplicate event identity")
            supplied_observation = _observation(
                _decode(event["observation_json"], "stored observation")
            )
            selected = _candidate(proposal, event["experiment_id"])
            update = _decode(event["update_json"], "stored update")
            expected_update = revise_model(
                {
                    "model": parameters["model"],
                    "experiment": selected,
                    "observation": supplied_observation,
                }
            )
            if update != expected_update:
                raise ValueError("Stored posterior contradicts observation")
            outcome = notes.get(event["outcome_note_id"])
            replacement = notes.get(event["model_note_id"])
            if (
                outcome is None
                or replacement is None
                or (
                    outcome["kind"] != "outcome"
                    or outcome["status"] != "observed"
                    or outcome["content"] != supplied_observation["note"]
                    or outcome["source"] != supplied_observation["source"]
                    or outcome["depends_on"] != []
                    or outcome["created_at"] != event["created_at"]
                    or replacement["kind"] != "forecast"
                    or replacement["status"] != "computed"
                    or replacement["source"] != f"compass-c:experiment-observation:{event['id']}"
                    or replacement["content"] != f"Posterior model for experiment plan {plan_id}."
                    or replacement["depends_on"] != anchor["depends_on"] + [outcome["id"]]
                    or replacement["created_at"] != event["created_at"]
                    or not anchor["stale"]
                )
            ):
                raise ValueError("Stored observation notes contradict its history")
            links = [link for link in snapshot["revisions"] if link["supersedes"] == anchor["id"]]
            if (
                len(links) != 1
                or links[0]["note_id"] != replacement["id"]
                or links[0]["revision"] != event["revision"]
            ):
                raise ValueError("Missing model replacement history")
            invalidations = [
                item
                for item in snapshot["invalidations"]
                if item["root_id"] == anchor["id"] and item["revision"] == event["revision"]
            ]
            if len(invalidations) != 1:
                raise ValueError("Missing model invalidation")
            receipt = {
                "plan_id": plan_id,
                "decision_id": row["decision_id"],
                "event_id": event["event_id"],
                "experiment_id": event["experiment_id"],
                "revision": event["revision"],
                "current_revision": snapshot["revision"],
                "applied": False,
                "replayed": True,
                "outcome_note_id": event["outcome_note_id"],
                "model_note_id": event["model_note_id"],
                "update": update,
                "invalidated": invalidations[0]["affected_notes"],
                "summary": _update_summary(update),
                **_BOUNDARY,
            }
            current_model = update["result"]["model"]
            current_model_note_id = replacement["id"]
            current_model_stale = replacement["stale"]
            receipt["current_model_stale"] = current_model_stale
            if current_model_stale:
                receipt["summary"]["next_action"] = (
                    "This receipt retains a historical update whose model is now stale. "
                    "Review changed evidence and freeze a new plan."
                )
        status = (
            "needs_replan"
            if current_model_stale
            else "observed"
            if receipt is not None
            else "awaiting_observation"
            if proposal["result"]["proposed_experiment_ids"]
            else "no_informative_experiment"
        )
        result = {
            "plan_id": plan_id,
            "decision_id": row["decision_id"],
            "revision": snapshot["revision"],
            "plan_revision": row["revision"],
            "model_note_id": row["model_note_id"],
            "parameters": parameters,
            "proposal": proposal,
            "current_model": current_model,
            "current_model_note_id": current_model_note_id,
            "current_model_stale": current_model_stale,
            "status": status,
            "observation": receipt,
            **_BOUNDARY,
        }
        result["summary"] = _plan_summary(result)
        return result, snapshot
    except (CompassError, ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
        raise CompassError("INVALID_STORAGE", "Malformed stored experiment lifecycle") from exc


def plan_experiment(
    book: Notebook,
    decision_id: str,
    expected_revision: int,
    parameters: dict,
    depends_on: list[str] | None = None,
) -> dict:
    """Freeze a bounded model and candidate protocols without executing them."""
    encoded = _encode(parameters, "parameters")
    frozen = json.loads(encoded)
    proposal = propose_experiments(frozen)
    encoded_proposal = _encode(proposal, "proposal")
    plan_id, note_id, timestamp = uuid.uuid4().hex, uuid.uuid4().hex, utc()
    with book._existing_connection(writable=True) as database:
        _require_schema(book, database)
        snapshot = book._snapshot(database, decision_id)
        book._revision(snapshot, expected_revision)
        dependencies = _dependencies(snapshot, depends_on)
        if (
            len(snapshot["notes"]) >= 2_000
            or database.execute(
                "SELECT COUNT(*) FROM experiment_plans WHERE decision_id=?", (decision_id,)
            ).fetchone()[0]
            >= _PLAN_LIMIT
        ):
            raise CompassError("CAPACITY", "Decision experiment or note limit reached")
        database.execute(
            "INSERT INTO notes VALUES (?, ?, 'forecast', ?, 'computed', ?, ?, 0, ?)",
            (
                note_id,
                decision_id,
                f"Frozen model for experiment plan {plan_id}.",
                f"compass-c:experiment-plan:{plan_id}",
                json.dumps(dependencies),
                timestamp,
            ),
        )
        database.execute(
            "INSERT INTO experiment_plans VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                plan_id,
                decision_id,
                note_id,
                encoded,
                encoded_proposal,
                expected_revision + 1,
                timestamp,
            ),
        )
        database.execute(
            "UPDATE decisions SET revision=? WHERE id=?", (expected_revision + 1, decision_id)
        )
        result, _ = _load(book, database, plan_id)
        return result


def experiment(book: Notebook, plan_id: str) -> dict:
    """Resume one frozen plan and its retained observation from a read-only snapshot."""
    with book._existing_connection(writable=False) as database:
        return _load(book, database, plan_id)[0]


def experiments(book: Notebook, decision_id: str) -> dict:
    """List concise plan summaries within a single decision snapshot."""
    with book._existing_connection(writable=False) as database:
        return _experiments_snapshot(book, database, decision_id)


def _experiments_snapshot(book: Notebook, database: sqlite3.Connection, decision_id: str) -> dict:
    """Read summaries inside the caller's transaction, including a decision brief."""
    _require_schema(book, database)
    snapshot = book._snapshot(database, decision_id)
    result = {
        "decision_id": decision_id,
        "revision": snapshot["revision"],
        "experiments": [],
        **_BOUNDARY,
    }
    rows = database.execute(
        "SELECT id FROM experiment_plans WHERE decision_id=? ORDER BY rowid", (decision_id,)
    ).fetchall()
    if len(rows) > _PLAN_LIMIT:
        raise CompassError("INVALID_STORAGE", "Stored experiment capacity exceeded")
    for row in rows:
        result["experiments"].append(lifecycle_view(_load(book, database, row["id"])[0]))
    orphan = database.execute(
        "SELECT 1 FROM experiment_observations AS o "
        "LEFT JOIN experiment_plans AS p ON o.plan_id=p.id "
        "WHERE o.decision_id=? AND (p.id IS NULL OR p.decision_id!=o.decision_id) LIMIT 1",
        (decision_id,),
    ).fetchone()
    if orphan is not None:
        raise CompassError("INVALID_STORAGE", "Orphaned experiment observation")
    return result


def _prepare(
    book: Notebook,
    database: sqlite3.Connection,
    plan_id: str,
    expected_revision: int,
    experiment_id: str,
    event_id: str,
    observation: dict,
) -> tuple[dict, dict, dict]:
    text(event_id, "event_id", limit=200)
    text(experiment_id, "experiment_id", limit=2_000)
    integer(expected_revision, "expected_revision", 1)
    supplied = _observation(observation)
    plan, snapshot = _load(book, database, plan_id)
    duplicate = database.execute(
        "SELECT plan_id FROM experiment_observations WHERE decision_id=? AND event_id=?",
        (plan["decision_id"], event_id),
    ).fetchone()
    if duplicate is not None:
        existing = _load(book, database, duplicate["plan_id"])[0]["observation"]
        if (
            duplicate["plan_id"] != plan_id
            or existing["experiment_id"] != experiment_id
            or existing["update"]["result"]["observation"] != supplied
        ):
            raise CompassError(
                "OBSERVATION_CONFLICT",
                "Event identity already names another observation in this decision",
            )
        return existing, plan, snapshot
    if plan["observation"] is not None:
        raise CompassError(
            "EXPERIMENT_COMPLETE",
            "This plan already incorporated one observation; freeze a new conditional plan",
        )
    book._revision(snapshot, expected_revision)
    if plan["status"] == "needs_replan":
        raise CompassError(
            "STALE_DEPENDENCY", "Experiment model depends on stale evidence; freeze a new plan"
        )
    selected = _candidate(plan["proposal"], experiment_id)
    update = revise_model(
        {"model": plan["parameters"]["model"], "experiment": selected, "observation": supplied}
    )
    _encode(update, "model update")
    if len(snapshot["notes"]) + 2 > 2_000:
        raise CompassError("CAPACITY", "Observation would exceed the decision note limit")
    affected = book._affected(snapshot["notes"], plan["model_note_id"])
    anchor = next(note for note in snapshot["notes"] if note["id"] == plan["model_note_id"])
    if affected.intersection(anchor["depends_on"]):
        raise CompassError("STALE_DEPENDENCY", "Model update would depend on invalidated reasoning")
    return (
        {
            "plan_id": plan_id,
            "decision_id": plan["decision_id"],
            "event_id": event_id,
            "experiment_id": experiment_id,
            "revision": snapshot["revision"],
            "current_revision": snapshot["revision"],
            "applied": False,
            "replayed": False,
            "update": update,
            "invalidated": sorted(affected),
            "summary": _update_summary(update),
            **_BOUNDARY,
        },
        plan,
        snapshot,
    )


def preview_observation(
    book: Notebook,
    plan_id: str,
    expected_revision: int,
    experiment_id: str,
    event_id: str,
    observation: dict,
) -> dict:
    """Show one sourced result's exact posterior and invalidations without writing."""
    with book._existing_connection(writable=False) as database:
        return _prepare(
            book, database, plan_id, expected_revision, experiment_id, event_id, observation
        )[0]


def apply_observation(
    book: Notebook,
    plan_id: str,
    expected_revision: int,
    experiment_id: str,
    event_id: str,
    observation: dict,
) -> dict:
    """Atomically retain one observation, posterior, and dependent-note invalidation."""
    with book._existing_connection(writable=True) as database:
        preview, plan, snapshot = _prepare(
            book, database, plan_id, expected_revision, experiment_id, event_id, observation
        )
        if preview["replayed"]:
            return preview
        event_row_id, outcome_id, replacement_id = (
            uuid.uuid4().hex,
            uuid.uuid4().hex,
            uuid.uuid4().hex,
        )
        timestamp, revision = utc(), expected_revision + 1
        reason = f"Incorporated experiment observation {event_row_id}."
        book._write_invalidation(
            database,
            plan["decision_id"],
            revision,
            plan["model_note_id"],
            reason,
            set(preview["invalidated"]),
        )
        observed = preview["update"]["result"]["observation"]
        anchor = next(note for note in snapshot["notes"] if note["id"] == plan["model_note_id"])
        database.execute(
            "INSERT INTO notes VALUES (?, ?, 'outcome', ?, 'observed', ?, '[]', 0, ?)",
            (outcome_id, plan["decision_id"], observed["note"], observed["source"], timestamp),
        )
        database.execute(
            "INSERT INTO notes VALUES (?, ?, 'forecast', ?, 'computed', ?, ?, 0, ?)",
            (
                replacement_id,
                plan["decision_id"],
                f"Posterior model for experiment plan {plan_id}.",
                f"compass-c:experiment-observation:{event_row_id}",
                json.dumps(anchor["depends_on"] + [outcome_id]),
                timestamp,
            ),
        )
        database.execute(
            "INSERT INTO note_revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                plan["decision_id"],
                plan["model_note_id"],
                replacement_id,
                reason,
                revision,
                timestamp,
            ),
        )
        database.execute(
            "INSERT INTO experiment_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_row_id,
                plan["decision_id"],
                plan_id,
                event_id,
                experiment_id,
                _encode(observed, "observation"),
                _encode(preview["update"], "update"),
                outcome_id,
                replacement_id,
                revision,
                timestamp,
            ),
        )
        receipt = _load(book, database, plan_id)[0]["observation"]
        receipt["applied"] = True
        receipt["replayed"] = False
        return receipt

"""BDD acceptance of real, fresh-process standalone CLI workflows."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from compass_c import CompassError, calculate

ROOT = Path(__file__).resolve().parents[1]


def invoke(db: Path, *args: str, portable: bool = False) -> tuple[int, dict]:
    entry = (
        ["-I", "-B", str(ROOT / "skills/compass/scripts/compass.py")]
        if portable
        else ["-m", "compass_c"]
    )
    process = subprocess.run(
        [sys.executable, *entry, "--db", str(db), *args],
        cwd=db.parent,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert not process.stderr, process.stderr
    return process.returncode, json.loads(process.stdout)


def success(db: Path, *args: str, portable: bool = False) -> dict:
    code, response = invoke(db, *args, portable=portable)
    assert code == 0, response
    assert response["ok"] is True
    return response["data"]


@pytest.mark.parametrize("portable", [False, True], ids=["package", "portable"])
def test_fresh_process_decision_journey(tmp_path: Path, portable: bool) -> None:
    db = tmp_path / "decisions.sqlite3"
    state = success(db, "start", "--objective", "Choose a bounded pilot", portable=portable)
    did, revision = state["decision_id"], state["revision"]
    evidence_id = decision_id = None
    notes = [
        ("evidence", "Pilot conversion is 0.12", "observed", "synthetic pilot run 1"),
        ("alternative", "Pilot", "proposed", ""),
        ("alternative", "Delay", "proposed", ""),
        ("test", "Replicate the pilot", "proposed", ""),
        ("limitation", "Small synthetic cohort", "assumed", ""),
        ("reversal_condition", "Conversion falls below 0.08", "proposed", ""),
        ("decision", "Prefer pilot while conversion exceeds 0.08", "inferred", ""),
    ]
    for kind, content, status, source in notes:
        state = success(
            db,
            "record",
            did,
            "--revision",
            str(revision),
            "--kind",
            kind,
            "--content",
            content,
            "--status",
            status,
            "--source",
            source,
            "--depends-on",
            json.dumps([evidence_id] if kind == "decision" else []),
            portable=portable,
        )
        revision = state["revision"]
        if kind == "evidence":
            evidence_id = state["note_id"]
        if kind == "decision":
            decision_id = state["note_id"]

    listing = success(db, "list", "--limit", "5", portable=portable)
    assert listing["total"] == 1
    assert listing["decisions"][0]["decision_id"] == did
    brief = success(db, "brief", did, portable=portable)
    assert brief["revision"] == revision
    assert brief["evidence"][0]["source"] == "synthetic pilot run 1"
    assert brief["reversal_conditions"][0]["content"] == "Conversion falls below 0.08"
    assert brief["review"]["status"] == "record_complete_not_verified"
    assert brief["action_permission"] == "not_granted"

    changed = success(
        db,
        "revise",
        did,
        evidence_id,
        "--revision",
        str(revision),
        "--content",
        "Pilot conversion is 0.04",
        "--reason",
        "Corrected denominator",
        "--status",
        "observed",
        "--source",
        "synthetic pilot run 2",
        portable=portable,
    )
    assert changed["revision"] == revision + 1
    assert decision_id in changed["invalidated"]
    brief = success(db, "brief", did, portable=portable)
    assert brief["review"]["status"] == "needs_work"
    assert brief["recommendations"] == []
    assert brief["evidence"][0]["content"] == "Pilot conversion is 0.04"
    assert evidence_id in {note["id"] for note in brief["stale_notes"]}
    assert brief["action_permission"] == "not_granted"


@pytest.mark.parametrize("portable", [False, True], ids=["package", "portable"])
def test_cli_sensitivity_has_no_storage(tmp_path: Path, portable: bool) -> None:
    db = tmp_path / "absent" / "decisions.sqlite3"
    # Use an existing working directory independently of the nonexistent DB parent.
    db.parent.mkdir()
    params = {
        "actions": ["pilot", "delay"],
        "scenarios": ["success", "failure"],
        "payoffs": [[10, -10], [0, 0]],
        "probability_start": [0, 1],
        "probability_end": [1, 0],
    }
    output = success(
        db, "calculate", "sensitivity", "--parameters", json.dumps(params), portable=portable
    )
    assert output["result"]["breakpoints"][0]["t"] == pytest.approx(0.5)
    assert output["action_permission"] == "not_granted"
    assert list(db.parent.iterdir()) == []


@pytest.mark.parametrize("command", ["list", "migrate"])
def test_missing_notebook_new_commands_do_not_initialize(tmp_path: Path, command: str) -> None:
    db = tmp_path / "missing.sqlite3"
    code, result = invoke(db, command)
    assert code == 2
    assert result["error"]["code"] == "STORAGE_NOT_FOUND"
    assert not db.exists()


def test_cli_evaluate_missing_file_is_bounded(tmp_path: Path) -> None:
    db = tmp_path / "missing.sqlite3"
    code, result = invoke(db, "evaluate", "--corpus", "missing.json", "--results", "no.json")
    assert code == 2
    assert result["error"]["code"] == "INPUT_FILE_ERROR"
    assert not db.exists()


@pytest.mark.parametrize("payload", [b"\xff", b'{"x": 1, "x": 2}', b"[" * 1500])
def test_cli_evaluate_invalid_input_has_no_traceback(tmp_path: Path, payload: bytes) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_bytes(payload)
    results = tmp_path / "results.json"
    results.write_text("{}")
    code, result = invoke(
        tmp_path / "missing.sqlite3", "evaluate", "--corpus", str(corpus), "--results", str(results)
    )
    assert code == 2
    assert result["error"]["code"] in {"INVALID_JSON", "INPUT_FILE_ERROR"}


DOCUMENTED_KINDS = (
    "compare",
    "sensitivity",
    "portfolio",
    "experiment",
    "update_beliefs",
    "committee",
    "bundle",
    "feedback",
    "recovery",
    "tail",
    "brier",
)


def test_unknown_calculation_names_every_supported_kind(tmp_path: Path) -> None:
    reference = (ROOT / "skills/compass/references/calculators.md").read_text(encoding="utf-8")
    assert tuple(re.findall(r"^\| ([a-z_]+) \|", reference, flags=re.MULTILINE)) == (
        DOCUMENTED_KINDS
    )
    code, response = invoke(
        tmp_path / "decisions.sqlite3", "calculate", "forecast", "--parameters", "{}"
    )
    assert code == 2
    assert response["error"]["code"] == "INVALID_ARGUMENTS"
    assert set(DOCUMENTED_KINDS) <= set(re.findall(r"[a-z_]+", response["error"]["message"]))
    with pytest.raises(CompassError) as error:
        calculate("forecast", {})
    assert error.value.code == "UNKNOWN_CALCULATION"
    assert set(DOCUMENTED_KINDS) <= set(re.findall(r"[a-z_]+", str(error.value)))
    assert not (tmp_path / ".compass").exists()


@pytest.mark.parametrize("portable", [False, True], ids=["package", "portable"])
def test_default_notebook_is_in_the_working_directory(tmp_path: Path, portable: bool) -> None:
    work, home = tmp_path / "work", tmp_path / "home"
    work.mkdir()
    home.mkdir()
    entry = (
        ["-I", "-B", str(ROOT / "skills/compass/scripts/compass.py")]
        if portable
        else ["-B", "-m", "compass_c"]
    )
    environment = {key: value for key, value in os.environ.items() if key != "COMPASS_DB"}
    environment["HOME"] = str(home)
    process = subprocess.run(
        [sys.executable, *entry, "start", "--objective", "Use the default location"],
        cwd=work,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout)["ok"] is True
    assert (work / ".compass" / "decisions.sqlite3").is_file()
    assert not any(home.iterdir())

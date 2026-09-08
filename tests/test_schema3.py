"""Executable compatibility scenarios for features/schema3.feature."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from compass_c import CompassError, Notebook
from compass_c.evidence import apply_updates, preview_updates

# Frozen DDL: legacy fixtures must not inherit changes to current initialization.
BASE_SCHEMA = """
CREATE TABLE compass_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE decisions (
    id TEXT PRIMARY KEY, objective TEXT NOT NULL, stakes TEXT NOT NULL,
    constraints_json TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE notes (
    id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES decisions(id),
    kind TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL,
    source TEXT NOT NULL, dependencies_json TEXT NOT NULL,
    stale INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE invalidations (
    id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES decisions(id),
    root_id TEXT NOT NULL, reason TEXT NOT NULL, affected_json TEXT NOT NULL,
    revision INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX notes_by_decision ON notes(decision_id);
"""
REVISION_SCHEMA = """
CREATE TABLE note_revisions (
    id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES decisions(id),
    supersedes TEXT NOT NULL REFERENCES notes(id), note_id TEXT NOT NULL REFERENCES notes(id),
    reason TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL
);
"""
PLAN_SCHEMA = """
CREATE TABLE experiment_plans (
    id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES decisions(id),
    model_note_id TEXT NOT NULL REFERENCES notes(id), parameters_json TEXT NOT NULL,
    proposal_json TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL
);
"""
OBSERVATION_COLUMNS = """
    id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES decisions(id),
    plan_id TEXT NOT NULL REFERENCES experiment_plans(id), event_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL, observation_json TEXT NOT NULL, update_json TEXT NOT NULL,
    outcome_note_id TEXT NOT NULL REFERENCES notes(id),
    model_note_id TEXT NOT NULL REFERENCES notes(id), revision INTEGER NOT NULL,
    created_at TEXT NOT NULL
"""
DID, NID = "a" * 32, "b" * 32


def legacy_notebook(tmp_path: Path, version: str) -> Notebook:
    path = tmp_path / f"schema-{version}.sqlite3"
    with sqlite3.connect(path) as database:
        database.executescript(BASE_SCHEMA)
        if version == "2":
            database.executescript(REVISION_SCHEMA)
        database.execute("INSERT INTO compass_meta VALUES ('schema_version', ?)", (version,))
        database.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
            (DID, "Keep the original evidence", "medium", '["Stay local"]', 2, "2026-01-01"),
        )
        database.execute(
            "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                NID,
                DID,
                "evidence",
                "Original source",
                "observed",
                "local:old",
                "[]",
                0,
                "2026-01-01",
            ),
        )
    return Notebook(path)


def stored_version(book: Notebook) -> str:
    with sqlite3.connect(book.path) as database:
        return database.execute(
            "SELECT value FROM compass_meta WHERE key='schema_version'"
        ).fetchone()[0]


def table_names(book: Notebook) -> set[str]:
    with sqlite3.connect(book.path) as database:
        return {
            row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_new_notebook_has_schema3_experiment_foreign_keys_and_uniqueness(tmp_path: Path) -> None:
    book = Notebook(tmp_path / "new.sqlite3")
    book.start("Plan an experiment")
    assert stored_version(book) == "3"
    assert {"experiment_plans", "experiment_observations"} <= table_names(book)
    with sqlite3.connect(book.path) as database:
        plan_links = {
            (row[3], row[2], row[4])
            for row in database.execute("PRAGMA foreign_key_list(experiment_plans)")
        }
        assert plan_links == {("decision_id", "decisions", "id"), ("model_note_id", "notes", "id")}
        observation_links = {
            (row[3], row[2], row[4])
            for row in database.execute("PRAGMA foreign_key_list(experiment_observations)")
        }
        assert observation_links == {
            ("decision_id", "decisions", "id"),
            ("plan_id", "experiment_plans", "id"),
            ("outcome_note_id", "notes", "id"),
            ("model_note_id", "notes", "id"),
        }
        unique_columns = {
            tuple(column[2] for column in database.execute(f'PRAGMA index_info("{row[1]}")'))
            for row in database.execute("PRAGMA index_list(experiment_observations)")
            if row[2]
        }
        assert {("decision_id", "event_id"), ("plan_id",)} <= unique_columns


@pytest.mark.parametrize("version", ["1", "2"])
def test_legacy_reads_and_start_do_not_silently_upgrade(tmp_path: Path, version: str) -> None:
    book = legacy_notebook(tmp_path, version)
    before = book.path.read_bytes()
    original = book.get(DID)
    assert book.brief(DID)["evidence"][0]["content"] == "Original source"
    assert book.list()["decisions"][0]["decision_id"] == DID
    assert book.path.read_bytes() == before
    book.start("Another decision in an existing notebook")
    assert stored_version(book) == version
    assert book.get(DID) == original
    assert not {"experiment_plans", "experiment_observations"} & table_names(book)


@pytest.mark.parametrize("version", ["1", "2"])
def test_legacy_record_and_invalidation_remain_available(tmp_path: Path, version: str) -> None:
    book = legacy_notebook(tmp_path, version)
    added = book.record(DID, 2, "assumption", "Derived claim", depends_on=[NID])
    result = book.invalidate(DID, 3, NID, "The source was withdrawn")
    assert set(result["invalidated"]) == {NID, added["note_id"]}
    assert stored_version(book) == version
    assert book.get(DID)["revision"] == 4


def test_schema2_revision_and_evidence_batches_do_not_require_schema3(tmp_path: Path) -> None:
    book = legacy_notebook(tmp_path, "2")
    revised = book.revise(
        DID, 2, NID, "Revised source", "A corrected observation", "observed", "local:revised"
    )
    updates = [
        {
            "note_id": revised["note_id"],
            "content": "Latest source",
            "reason": "A later observation",
            "status": "observed",
            "source": "local:latest",
        }
    ]
    before = book.path.read_bytes()
    preview = preview_updates(book, DID, 3, updates)
    assert preview["applied"] is False
    assert book.path.read_bytes() == before
    applied = apply_updates(book, DID, 3, updates)
    assert applied["revision"] == 4
    assert len(book.get(DID)["revisions"]) == 2
    assert stored_version(book) == "2"


@pytest.mark.parametrize("version", ["1", "2"])
def test_explicit_upgrade_to_schema3_preserves_every_historical_field(
    tmp_path: Path, version: str
) -> None:
    book = legacy_notebook(tmp_path, version)
    if version == "1":
        book.invalidate(DID, 2, NID, "Withdrawn before the upgrade")
    else:
        book.revise(DID, 2, NID, "Replacement before the upgrade", "Correct source")
    original = book.get(DID)
    result = book.migrate()
    assert result["from_version"] == version
    assert result["schema_version"] == "3"
    assert result["migrated"] is True
    assert result["action_permission"] == "not_granted"
    assert stored_version(book) == "3"
    assert book.get(DID) == original
    assert {"note_revisions", "experiment_plans", "experiment_observations"} <= table_names(book)
    after = book.path.read_bytes()
    assert book.migrate()["migrated"] is False
    assert book.path.read_bytes() == after


@pytest.mark.parametrize("version", ["1", "2"])
def test_failed_upgrade_rolls_back_created_tables_and_metadata(
    tmp_path: Path, version: str
) -> None:
    book = legacy_notebook(tmp_path, version)
    with sqlite3.connect(book.path) as database:
        database.execute(
            "CREATE TRIGGER refuse_upgrade BEFORE UPDATE ON compass_meta "
            "BEGIN SELECT RAISE(ABORT, 'upgrade refused'); END"
        )
    before = book.path.read_bytes()
    original_tables = table_names(book)
    with pytest.raises(CompassError):
        book.migrate()
    assert book.path.read_bytes() == before
    assert table_names(book) == original_tables
    assert stored_version(book) == version


@pytest.mark.parametrize("version", ["1", "2"])
def test_corrupt_legacy_history_cannot_be_migrated(tmp_path: Path, version: str) -> None:
    book = legacy_notebook(tmp_path, version)
    with sqlite3.connect(book.path) as database:
        database.execute("UPDATE notes SET source='' WHERE id=?", (NID,))
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        book.migrate()
    assert error.value.code == "INVALID_STORAGE"
    assert book.path.read_bytes() == before
    assert stored_version(book) == version
    assert not {"experiment_plans", "experiment_observations"} & table_names(book)


@pytest.mark.parametrize("operation", ["get", "migrate"])
@pytest.mark.parametrize("missing", ["event", "plan"])
def test_schema3_without_required_observation_uniqueness_is_refused(
    tmp_path: Path, operation: str, missing: str
) -> None:
    book = legacy_notebook(tmp_path, "2")
    retained_constraint = (
        "UNIQUE(plan_id)" if missing == "event" else "UNIQUE(decision_id,event_id)"
    )
    with sqlite3.connect(book.path) as database:
        database.executescript(PLAN_SCHEMA)
        database.execute(
            "CREATE TABLE experiment_observations ("
            + OBSERVATION_COLUMNS
            + ", "
            + retained_constraint
            + ")"
        )
        database.execute("UPDATE compass_meta SET value='3' WHERE key='schema_version'")
    before = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        getattr(book, operation)(*([DID] if operation == "get" else []))
    assert error.value.code == "INVALID_STORAGE"
    assert book.path.read_bytes() == before

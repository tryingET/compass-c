from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from compass_c import CompassError, Notebook

# Frozen schema-1 fixture: deliberately independent of current runtime schema code.
LEGACY_SCHEMA = """
CREATE TABLE compass_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO compass_meta VALUES ('schema_version', '1');
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
DID, NID = "a" * 32, "b" * 32


@pytest.fixture
def legacy(tmp_path: Path) -> Notebook:
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(LEGACY_SCHEMA)
        db.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
            (DID, "Retain a legacy decision", "medium", '["No remote writes"]', 2, "2026-01-01"),
        )
        db.execute(
            "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (NID, DID, "evidence", "Exact legacy source", "observed", "local:old", "[]", 0,
             "2026-01-01"),
        )
    return Notebook(path)


@pytest.fixture
def decision(tmp_path: Path) -> tuple[Notebook, str]:
    book = Notebook(tmp_path / "notebook.sqlite3")
    did = book.start("Choose an architecture", constraints=["Keep records local"])["decision_id"]
    return book, did


def add(book: Notebook, did: str, kind: str, content: str, **kwargs: object) -> str:
    return book.record(did, book.get(did)["revision"], kind, content, **kwargs)["note_id"]


def test_brief_preserves_sections_provenance_and_bytes(decision: tuple[Notebook, str]) -> None:
    book, did = decision
    fields = {
        "evidence": "evidence", "alternative": "alternatives", "decision": "recommendations",
        "assumption": "uncertainty", "forecast": "uncertainty", "limitation": "uncertainty",
        "test": "checks", "effect": "effects", "reversal_condition": "reversal_conditions",
        "outcome": "outcomes",
    }
    for kind in fields:
        add(book, did, kind, f"  Exact {kind}\nsource-preserving text  ",
            status="observed", source="file:///local/original#p2")
    add(book, did, "alternative", "Wait and gather more evidence")
    snapshot = book.get(did)
    before = book.path.read_bytes()
    brief = book.brief(did)
    assert book.path.read_bytes() == before
    assert brief["revision"] == snapshot["revision"]
    assert brief["objective"] == snapshot["objective"]
    assert brief["constraints"] == ["Keep records local"]
    for kind, field in fields.items():
        expected = [note for note in snapshot["notes"] if note["kind"] == kind]
        assert [note for note in brief[field] if note["kind"] == kind] == expected
    assert brief["review"]["status"] == "record_complete_not_verified"
    assert brief["review"]["source_verified"] is False
    assert brief["source_verified"] is False
    assert brief["scope"] == "analysis_only"
    assert brief["action_permission"] == "not_granted"


def test_brief_keeps_stale_material_out_of_recommendations(decision: tuple[Notebook, str]) -> None:
    book, did = decision
    evidence = add(book, did, "evidence", "Source changed", status="observed", source="local:test")
    rec = add(book, did, "decision", "Old conclusion", depends_on=[evidence])
    book.invalidate(did, book.get(did)["revision"], evidence, "New observation")
    brief = book.brief(did)
    assert brief["recommendations"] == []
    assert brief["evidence"] == []
    assert {note["id"] for note in brief["stale_notes"]} == {evidence, rec}
    assert brief["review"]["status"] == "needs_work"
    assert any("reversal" in gap.lower() for gap in brief["review"]["next_checks"])


def test_revision_appends_history_and_invalidates_transitively(decision: tuple[Notebook, str]) -> None:
    book, did = decision
    root = add(book, did, "evidence", "Old finding", status="observed", source="local:v1")
    derived = add(book, did, "assumption", "Derived", depends_on=[root])
    dependent = add(book, did, "test", "Follow-up", depends_on=[derived])
    rec = add(book, did, "decision", "Unlinked conditional recommendation")
    untouched = add(book, did, "alternative", "Independent alternative")
    before = book.get(did)
    result = book.revise(did, before["revision"], root, "New finding", "Evidence updated",
                         status="observed", source="local:v2")
    after = book.get(did)
    notes = {note["id"]: note for note in after["notes"]}
    assert result["revision"] == after["revision"] == before["revision"] + 1
    assert result["supersedes"] == root
    assert set(result["invalidated"]) == {root, derived, dependent, rec}
    old = next(note for note in before["notes"] if note["id"] == root)
    assert notes[root] == {**old, "stale": True}
    assert notes[untouched]["stale"] is False
    assert notes[result["note_id"]]["content"] == "New finding"
    assert notes[result["note_id"]]["source"] == "local:v2"
    assert notes[result["note_id"]]["kind"] == "evidence"
    assert notes[result["note_id"]]["stale"] is False
    history = after["revisions"]
    assert len(history) == 1
    assert history[0]["supersedes"] == root
    assert history[0]["note_id"] == result["note_id"]
    assert history[0]["reason"] == "Evidence updated"
    assert history[0]["revision"] == after["revision"]
    assert after["invalidations"][0]["reason"] == "Evidence updated"
    assert result["action_permission"] == "not_granted"


def test_revision_preserves_dependencies_when_omitted(decision: tuple[Notebook, str]) -> None:
    book, did = decision
    basis = add(book, did, "assumption", "Independent basis")
    target = add(book, did, "evidence", "Derived result", depends_on=[basis])
    result = book.revise(did, book.get(did)["revision"], target, "New result", "Recomputed")
    replacement = next(n for n in book.get(did)["notes"] if n["id"] == result["note_id"])
    assert replacement["depends_on"] == [basis]


@pytest.mark.parametrize("failure", ["stale", "self", "dependent", "revision", "source", "reason"])
def test_failed_revision_is_atomic(decision: tuple[Notebook, str], failure: str) -> None:
    book, did = decision
    root = add(book, did, "evidence", "Old source")
    descendant = add(book, did, "test", "Derived check", depends_on=[root])
    stale = add(book, did, "assumption", "Withdrawn assumption")
    book.invalidate(did, book.get(did)["revision"], stale, "Withdrawn")
    snapshot = book.get(did)
    before = book.path.read_bytes()
    kwargs: dict[str, object] = {}
    rev = snapshot["revision"]
    reason = "Updated"
    expected = "STALE_DEPENDENCY"
    if failure in {"stale", "self", "dependent"}:
        kwargs["depends_on"] = [{"stale": stale, "self": root, "dependent": descendant}[failure]]
    elif failure == "revision":
        rev -= 1
        expected = "REVISION_CONFLICT"
    elif failure == "source":
        kwargs["status"] = "observed"
        expected = "SOURCE_REQUIRED"
    elif failure == "reason":
        reason = ""
        expected = "INVALID_INPUT"
    with pytest.raises(CompassError) as error:
        book.revise(did, rev, root, "Replacement", reason, **kwargs)
    assert error.value.code == expected
    assert book.get(did) == snapshot
    assert book.path.read_bytes() == before


def test_legacy_reads_do_not_migrate_and_explicit_upgrade_preserves_history(legacy: Notebook) -> None:
    before = legacy.path.read_bytes()
    original = legacy.get(DID)
    assert legacy.brief(DID)["evidence"][0]["content"] == "Exact legacy source"
    assert legacy.list()["decisions"][0]["decision_id"] == DID
    assert legacy.path.read_bytes() == before
    with pytest.raises(CompassError) as error:
        legacy.revise(DID, 2, NID, "Changed", "Explicit update")
    assert error.value.code == "MIGRATION_REQUIRED"
    assert legacy.path.read_bytes() == before
    migration = legacy.migrate()
    assert migration["from_version"] == "1"
    assert migration["schema_version"] == "2"
    assert migration["migrated"] is True
    assert migration["action_permission"] == "not_granted"
    assert legacy.get(DID) == original
    after = legacy.path.read_bytes()
    assert legacy.migrate()["migrated"] is False
    assert legacy.path.read_bytes() == after
    assert legacy.revise(DID, 2, NID, "New fact", "New evidence")["revision"] == 3


@pytest.mark.parametrize("operation", ["get", "brief", "list", "migrate"])
@pytest.mark.parametrize("damage", ["newer", "missing_table", "bad_json", "bad_revision"])
def test_unusable_notebooks_are_refused_without_mutation(
    legacy: Notebook, operation: str, damage: str,
) -> None:
    with sqlite3.connect(legacy.path) as db:
        if damage == "newer":
            db.execute("UPDATE compass_meta SET value='999' WHERE key='schema_version'")
        elif damage == "missing_table":
            db.execute("DROP TABLE notes")
        elif damage == "bad_json":
            db.execute("UPDATE decisions SET constraints_json='not JSON'")
        else:
            db.execute("UPDATE decisions SET revision=-1")
    before = legacy.path.read_bytes()
    with pytest.raises(CompassError) as error:
        getattr(legacy, operation)(*([DID] if operation in {"get", "brief"} else []))
    assert error.value.code == ("UNSUPPORTED_SCHEMA" if damage == "newer" else "INVALID_STORAGE")
    assert legacy.path.read_bytes() == before


def test_migration_failure_rolls_back_schema_and_metadata(legacy: Notebook) -> None:
    with sqlite3.connect(legacy.path) as db:
        db.execute("CREATE TRIGGER refuse_upgrade BEFORE UPDATE ON compass_meta "
                   "BEGIN SELECT RAISE(ABORT, 'upgrade blocked'); END")
    before = legacy.path.read_bytes()
    with pytest.raises(CompassError):
        legacy.migrate()
    assert legacy.path.read_bytes() == before
    with sqlite3.connect(legacy.path) as db:
        assert db.execute("SELECT value FROM compass_meta").fetchone()[0] == "1"
        assert db.execute("SELECT name FROM sqlite_master WHERE name='note_revisions'").fetchone() is None


def test_concurrent_initial_starts_keep_every_decision(tmp_path: Path) -> None:
    path = tmp_path / "simultaneous.sqlite3"
    barrier = Barrier(8)

    def start(index: int) -> str:
        barrier.wait()
        return Notebook(path).start(f"Concurrent objective {index}")["decision_id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(start, range(8)))
    listed = Notebook(path).list()
    assert listed["total"] == 8
    assert {item["decision_id"] for item in listed["decisions"]} == set(ids)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_competing_revisions_accept_exactly_one(decision: tuple[Notebook, str]) -> None:
    book, did = decision
    root = add(book, did, "assumption", "Original")
    barrier = Barrier(6)

    def revise(index: int) -> str:
        barrier.wait()
        try:
            return book.revise(did, 2, root, f"Candidate {index}", "Competing update")["note_id"]
        except CompassError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(revise, range(6)))
    assert results.count("REVISION_CONFLICT") == 5
    final = book.get(did)
    assert final["revision"] == 3
    assert len(final["notes"]) == 2
    assert len(final["revisions"]) == len(final["invalidations"]) == 1


def test_list_is_bounded_recent_and_read_only(decision: tuple[Notebook, str]) -> None:
    book, original = decision
    second = book.start("Second")["decision_id"]
    third = book.start("Third")["decision_id"]
    before = book.path.read_bytes()
    page = book.list(limit=1, offset=1)
    assert page["total"] == 3
    assert page["limit"] == page["offset"] == 1
    assert [row["decision_id"] for row in page["decisions"]] == [second]
    assert [row["decision_id"] for row in book.list()["decisions"]] == [third, second, original]
    assert "notes" not in page["decisions"][0]
    assert page["action_permission"] == "not_granted"
    assert book.path.read_bytes() == before
    for kwargs in ({"limit": 0}, {"limit": True}, {"offset": -1}, {"limit": 101}):
        with pytest.raises(CompassError):
            book.list(**kwargs)


@pytest.mark.parametrize("operation", ["brief", "list", "migrate"])
def test_new_operations_do_not_create_missing_storage(tmp_path: Path, operation: str) -> None:
    path = tmp_path / "absent" / "notebook.sqlite3"
    with pytest.raises(CompassError) as error:
        getattr(Notebook(path), operation)(*([DID] if operation == "brief" else []))
    assert error.value.code == "STORAGE_NOT_FOUND"
    assert not path.parent.exists()

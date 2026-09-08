"""Executable scenarios for explicit, atomic living-evidence updates."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from compass_c import CompassError, Notebook
from compass_c.evidence import apply_updates, preview_updates


@pytest.fixture
def decision(tmp_path: Path) -> tuple[Notebook, str, dict[str, str]]:
    book = Notebook(tmp_path / "evidence.sqlite3")
    did = book.start("Decide whether the release is ready")["decision_id"]
    ids = {}

    def record(name: str, kind: str, content: str, **kwargs: object) -> str:
        ids[name] = book.record(did, book.get(did)["revision"], kind, content, **kwargs)["note_id"]
        return ids[name]

    record("tests", "evidence", "Tests have not run", status="observed", source="local:old-log")
    record("install", "evidence", "Installation has not run")
    record("derived", "assumption", "Build may work", depends_on=[ids["tests"]])
    record("recommendation", "decision", "Wait for independent evidence")
    record("reversal", "reversal_condition", "Reconsider if the wheel cannot execute")
    record("outcome", "outcome", "No host usefulness study yet")
    record("independent", "alternative", "Delay release")
    return book, did, ids


def update(note_id: str, **kwargs: object) -> dict[str, object]:
    return {
        "note_id": note_id,
        "content": "  Exact measured result\n日本語 🌌  ",
        "reason": "New caller-supplied observation",
        "status": "observed",
        "source": "https://example.invalid/not-fetched#result",
        **kwargs,
    }


def test_preview_is_read_only_source_faithful_and_exposes_review(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    before = book.get(did)
    before_bytes = book.path.read_bytes()
    batch = [update(ids["tests"]), update(ids["install"], status="computed")]
    result = preview_updates(book, did, before["revision"], batch)
    assert result["applied"] is False
    assert result["revision"] == before["revision"]
    assert result["decision_id"] == did
    assert set(result["invalidated"]) == {
        ids["tests"],
        ids["install"],
        ids["derived"],
        ids["recommendation"],
    }
    assert [entry["content"] for entry in result["updates"]] == [x["content"] for x in batch]
    assert [entry["source"] for entry in result["updates"]] == [x["source"] for x in batch]
    for field, kind in [("reversal_conditions", "reversal_condition"), ("outcomes", "outcome")]:
        assert result["review"][field] == [n for n in before["notes"] if n["kind"] == kind]
    assert result["review"]["conditions_evaluated"] is False
    assert result["review"]["status"] == "human_review_required"
    assert result["source_verified"] is False
    assert result["scope"] == "analysis_only"
    assert result["action_permission"] == "not_granted"
    assert book.get(did) == before
    assert book.path.read_bytes() == before_bytes


def test_apply_replaces_entire_batch_in_one_revision_preserving_history(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    before = book.get(did)
    batch = [update(ids["tests"]), update(ids["install"])]
    expected = preview_updates(book, did, before["revision"], batch)
    result = apply_updates(book, did, before["revision"], batch)
    after = book.get(did)
    notes = {n["id"]: n for n in after["notes"]}
    assert result["applied"] is True
    assert result["revision"] == after["revision"] == before["revision"] + 1
    assert result["invalidated"] == expected["invalidated"]
    assert len(after["notes"]) == len(before["notes"]) + 2
    for original in before["notes"]:
        assert notes[original["id"]] == {
            **original,
            "stale": original["id"] in expected["invalidated"],
        }
    assert len(after["revisions"]) == len(after["invalidations"]) == 2
    for entry, requested in zip(result["updates"], batch, strict=True):
        replacement = notes[entry["note_id"]]
        assert replacement["id"] != requested["note_id"]
        assert replacement["content"] == requested["content"]
        assert replacement["source"] == requested["source"]
        assert replacement["stale"] is False
        assert entry["supersedes"] == requested["note_id"]
        history = next(h for h in after["revisions"] if h["note_id"] == entry["note_id"])
        assert history["supersedes"] == requested["note_id"]
        assert history["revision"] == after["revision"]
        assert history["reason"] == requested["reason"]
    assert result["action_permission"] == "not_granted"
    assert result["source_verified"] is False
    assert book.brief(did)["recommendations"] == []


@pytest.mark.parametrize("operation", [preview_updates, apply_updates])
@pytest.mark.parametrize(
    ("failure", "code"),
    [
        ("source", "SOURCE_REQUIRED"),
        ("reason", "INVALID_INPUT"),
        ("unknown_field", "INVALID_INPUT"),
        ("missing_field", "INVALID_INPUT"),
        ("status", "INVALID_INPUT"),
        ("content", "INVALID_INPUT"),
        ("not_found", "NOT_FOUND"),
        ("duplicate_root", "INVALID_INPUT"),
        ("changed_dependency", "STALE_DEPENDENCY"),
        ("unknown_dependency", "INVALID_DEPENDENCY"),
        ("duplicate_dependency", "INVALID_INPUT"),
        ("recommendation", "INVALID_INPUT"),
        ("superseded", "NOTE_SUPERSEDED"),
    ],
)
def test_invalid_member_refuses_entire_batch(
    decision: tuple[Notebook, str, dict[str, str]], operation: object, failure: str, code: str
) -> None:
    book, did, ids = decision
    batch = [update(ids["tests"]), update(ids["install"])]
    second = batch[1]
    if failure == "source":
        second["source"] = " "
    elif failure == "reason":
        second["reason"] = ""
    elif failure == "unknown_field":
        second["fetch_source"] = True
    elif failure == "missing_field":
        second.pop("source")
    elif failure == "status":
        second["status"] = "inferred"
    elif failure == "content":
        second["content"] = "broken \ud800"
    elif failure == "not_found":
        second["note_id"] = "f" * 32
    elif failure == "duplicate_root":
        second["note_id"] = ids["tests"]
    elif failure == "changed_dependency":
        second["depends_on"] = [ids["derived"]]
    elif failure == "unknown_dependency":
        second["depends_on"] = ["f" * 32]
    elif failure == "duplicate_dependency":
        second["depends_on"] = [ids["independent"], ids["independent"]]
    elif failure == "recommendation":
        second["note_id"] = ids["recommendation"]
    elif failure == "superseded":
        book.revise(did, book.get(did)["revision"], ids["install"], "Updated", "Prior update")
    before = book.get(did)
    before_bytes = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        operation(book, did, before["revision"], batch)
    assert error.value.code == code
    assert book.get(did) == before
    assert book.path.read_bytes() == before_bytes


@pytest.mark.parametrize("batch", [None, [], {}, [1], [update("f" * 32)] * 65])
def test_batches_are_explicit_nonempty_and_bounded(
    decision: tuple[Notebook, str, dict[str, str]], batch: object
) -> None:
    book, did, _ = decision
    before = book.get(did)
    with pytest.raises(CompassError) as error:
        apply_updates(book, did, before["revision"], batch)
    assert error.value.code == "INVALID_INPUT"
    assert book.get(did) == before


def test_apply_rechecks_revision_after_preview(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    revision = book.get(did)["revision"]
    batch = [update(ids["tests"])]
    preview_updates(book, did, revision, batch)
    book.record(did, revision, "limitation", "A concurrent owner changed the decision")
    before = book.get(did)
    with pytest.raises(CompassError) as error:
        apply_updates(book, did, revision, batch)
    assert error.value.code == "REVISION_CONFLICT"
    assert book.get(did) == before
    with pytest.raises(CompassError) as error:
        apply_updates(book, did, True, batch)
    assert error.value.code == "INVALID_INPUT"


def test_late_database_failure_rolls_back_every_batch_member(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    with sqlite3.connect(book.path) as database:
        database.execute(
            "CREATE TRIGGER reject_second_history BEFORE INSERT ON note_revisions "
            "WHEN (SELECT COUNT(*) FROM note_revisions) >= 1 "
            "BEGIN SELECT RAISE(ABORT, 'later history failed'); END"
        )
    before = book.get(did)
    before_bytes = book.path.read_bytes()
    with pytest.raises(CompassError):
        apply_updates(book, did, before["revision"], [update(ids["tests"]), update(ids["install"])])
    assert book.get(did) == before
    assert book.path.read_bytes() == before_bytes


def test_only_one_competing_batch_commits(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    before = book.get(did)
    barrier = Barrier(4)

    def apply(index: int) -> str:
        barrier.wait()
        try:
            result = apply_updates(
                book,
                did,
                before["revision"],
                [
                    update(ids["tests"], content=f"Tests from writer {index}"),
                    update(ids["install"]),
                ],
            )
            return result["updates"][0]["note_id"]
        except CompassError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(apply, range(4)))
    assert results.count("REVISION_CONFLICT") == 3
    after = book.get(did)
    assert after["revision"] == before["revision"] + 1
    assert len(after["notes"]) == len(before["notes"]) + 2
    assert len(after["revisions"]) == 2


def test_outcome_updates_remain_sourced_and_need_explicit_review(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    result = apply_updates(book, did, book.get(did)["revision"], [update(ids["outcome"])])
    outcomes = result["review"]["outcomes"]
    assert len(outcomes) == 2
    assert outcomes[0]["stale"] is True
    assert outcomes[1]["id"] == result["updates"][0]["note_id"]
    assert outcomes[1]["stale"] is False
    assert result["review"]["conditions_evaluated"] is False


def test_omitted_dependencies_are_preserved_when_current(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    result = apply_updates(book, did, book.get(did)["revision"], [update(ids["derived"])])
    assert result["updates"][0]["depends_on"] == [ids["tests"]]


@pytest.mark.parametrize("operation", [preview_updates, apply_updates])
def test_missing_storage_is_not_created(tmp_path: Path, operation: object) -> None:
    path = tmp_path / "missing" / "notebook.sqlite3"
    with pytest.raises(CompassError) as error:
        operation(Notebook(path), "a" * 32, 1, [update("b" * 32)])
    assert error.value.code == "STORAGE_NOT_FOUND"
    assert not path.parent.exists()


@pytest.mark.parametrize("operation", [preview_updates, apply_updates])
def test_legacy_schema_requires_explicit_migration(
    decision: tuple[Notebook, str, dict[str, str]], operation: object
) -> None:
    book, did, ids = decision
    revision = book.get(did)["revision"]
    with sqlite3.connect(book.path) as database:
        database.execute("DROP TABLE note_revisions")
        database.execute("UPDATE compass_meta SET value='1' WHERE key='schema_version'")
    before_bytes = book.path.read_bytes()
    with pytest.raises(CompassError) as error:
        operation(book, did, revision, [update(ids["tests"])])
    assert error.value.code == "MIGRATION_REQUIRED"
    assert book.path.read_bytes() == before_bytes


def test_capacity_is_checked_for_whole_batch(
    decision: tuple[Notebook, str, dict[str, str]],
) -> None:
    book, did, ids = decision
    with sqlite3.connect(book.path) as database:
        for index in range(1999 - len(book.get(did)["notes"])):
            database.execute(
                "INSERT INTO notes VALUES (?, ?, 'assumption', 'Capacity fixture', "
                "'proposed', '', '[]', 0, 'fixture')",
                (f"{index:032x}", did),
            )
    before = book.get(did)
    with pytest.raises(CompassError) as error:
        apply_updates(book, did, before["revision"], [update(ids["tests"]), update(ids["install"])])
    assert error.value.code == "CAPACITY"
    assert book.get(did) == before

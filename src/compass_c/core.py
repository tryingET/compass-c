"""Local COMPASS-C decision notebook.

The notebook is advisory only. It never grants action permission. Construction and
reads are side-effect free; only a validated ``start`` operation may initialize a
new SQLite database.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VERSION = "0.5.0"
SCHEMA_VERSION = "3"
KINDS = {
    "assumption",
    "evidence",
    "alternative",
    "test",
    "effect",
    "forecast",
    "decision",
    "outcome",
    "limitation",
    "reversal_condition",
}
STATUSES = {"assumed", "observed", "computed", "inferred", "proposed"}
STAKES = {"low", "medium", "high"}


class CompassError(ValueError):
    """Stable, machine-readable COMPASS-C failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def text(value: Any, field: str, *, limit: int = 12_000, empty: bool = False) -> str:
    if type(value) is not str or (not empty and not value.strip()) or len(value) > limit:
        requirement = (
            f"{field} must be a nonempty string of at most {limit} characters"
            if not empty
            else f"invalid {field}"
        )
        raise CompassError("INVALID_INPUT", requirement)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CompassError("INVALID_INPUT", f"{field} must contain valid Unicode text") from exc
    return value


def integer(value: Any, field: str, minimum: int = 0, maximum: int = 1_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CompassError("INVALID_INPUT", f"{field} must be an integer in [{minimum}, {maximum}]")
    return value


def number(value: Any, field: str, minimum: float = -1e12, maximum: float = 1e12) -> float:
    if type(value) not in (int, float) or not minimum <= value <= maximum:
        raise CompassError("INVALID_INPUT", f"{field} must be finite and in [{minimum}, {maximum}]")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise CompassError("INVALID_INPUT", f"{field} must be finite and in [{minimum}, {maximum}]")
    return parsed


def strings(value: Any, field: str, *, maximum: int = 64) -> list[str]:
    if type(value) is not list or len(value) > maximum:
        raise CompassError("INVALID_INPUT", f"{field} must be a list of at most {maximum} strings")
    return [text(item, field, limit=2_000) for item in value]


def identifier(value: Any, field: str) -> str:
    parsed = text(value, field, limit=32)
    if len(parsed) != 32 or any(character not in "0123456789abcdef" for character in parsed):
        raise CompassError("INVALID_INPUT", f"{field} must be a generated 32-character identifier")
    return parsed


def utc() -> str:
    return datetime.now(UTC).isoformat()


class Notebook:
    """One workspace-owned SQLite notebook with optimistic revision checks."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().absolute()

    @contextmanager
    def _existing_connection(self, *, writable: bool) -> Iterator[sqlite3.Connection]:
        if not self.path.is_file():
            raise CompassError("STORAGE_NOT_FOUND", "COMPASS-C notebook does not exist")
        mode = "rw" if writable else "ro"
        try:
            database = sqlite3.connect(f"{self.path.as_uri()}?mode={mode}", uri=True, timeout=10)
        except sqlite3.Error as exc:
            raise CompassError(
                "INVALID_STORAGE", "Path is not a usable COMPASS-C notebook"
            ) from exc
        database.row_factory = sqlite3.Row
        try:
            database.execute("PRAGMA foreign_keys=ON")
            with database:
                database.execute("BEGIN IMMEDIATE" if writable else "BEGIN")
                self._verify_schema(database)
                yield database
        except sqlite3.Error as exc:
            code = (
                "STORAGE_ERROR" if isinstance(exc, sqlite3.OperationalError) else "INVALID_STORAGE"
            )
            raise CompassError(
                code, "Notebook operation failed; no changes were committed"
            ) from exc
        except OSError as exc:
            raise CompassError("STORAGE_ERROR", "Notebook storage is unavailable") from exc
        finally:
            database.close()

    @contextmanager
    def _start_connection(self) -> Iterator[sqlite3.Connection]:
        try:
            if not self.path.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                # Publish only a complete database. The hard link is an atomic,
                # no-overwrite claim, including across independent processes.
                descriptor, temporary = tempfile.mkstemp(
                    prefix=".compass-init-", suffix=".sqlite3", dir=self.path.parent
                )
                os.close(descriptor)
                try:
                    database = sqlite3.connect(temporary, timeout=10)
                    try:
                        with database:
                            database.execute("BEGIN IMMEDIATE")
                            self._initialize_schema(database)
                    finally:
                        database.close()
                    try:
                        os.link(temporary, self.path)
                    except FileExistsError:
                        pass  # Another valid start won; verify its database below.
                finally:
                    Path(temporary).unlink(missing_ok=True)
            with self._existing_connection(writable=True) as database:
                yield database
        except OSError as exc:
            raise CompassError("STORAGE_ERROR", "Notebook storage is unavailable") from exc
        except sqlite3.Error as exc:
            raise CompassError("STORAGE_ERROR", "Could not initialize notebook storage") from exc

    @staticmethod
    def _initialize_schema(database: sqlite3.Connection) -> None:
        statements = """
            CREATE TABLE compass_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO compass_meta VALUES ('schema_version', '3');
            CREATE TABLE decisions (
                id TEXT PRIMARY KEY, objective TEXT NOT NULL, stakes TEXT NOT NULL,
                constraints_json TEXT NOT NULL, revision INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE notes (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL REFERENCES decisions(id),
                kind TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL,
                source TEXT NOT NULL, dependencies_json TEXT NOT NULL,
                stale INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE invalidations (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL REFERENCES decisions(id),
                root_id TEXT NOT NULL, reason TEXT NOT NULL, affected_json TEXT NOT NULL,
                revision INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX notes_by_decision ON notes(decision_id);
            """
        # executescript commits implicitly, so execute each known DDL statement
        # inside the caller's transaction instead.
        for statement in statements.split(";"):
            if statement.strip():
                database.execute(statement)
        Notebook._revision_schema(database)
        Notebook._experiment_schema(database)

    @staticmethod
    def _experiment_schema(database: sqlite3.Connection) -> None:
        database.execute(
            """CREATE TABLE experiment_plans (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL REFERENCES decisions(id),
                model_note_id TEXT NOT NULL REFERENCES notes(id),
                parameters_json TEXT NOT NULL, proposal_json TEXT NOT NULL,
                revision INTEGER NOT NULL, created_at TEXT NOT NULL
            )"""
        )
        database.execute(
            """CREATE TABLE experiment_observations (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL REFERENCES decisions(id),
                plan_id TEXT NOT NULL REFERENCES experiment_plans(id),
                event_id TEXT NOT NULL, experiment_id TEXT NOT NULL,
                observation_json TEXT NOT NULL, update_json TEXT NOT NULL,
                outcome_note_id TEXT NOT NULL REFERENCES notes(id),
                model_note_id TEXT NOT NULL REFERENCES notes(id),
                revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(decision_id, event_id), UNIQUE(plan_id)
            )"""
        )

    @staticmethod
    def _revision_schema(database: sqlite3.Connection) -> None:
        database.execute(
            """CREATE TABLE note_revisions (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL REFERENCES decisions(id),
                supersedes TEXT NOT NULL REFERENCES notes(id),
                note_id TEXT NOT NULL REFERENCES notes(id),
                reason TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL
            )"""
        )

    @staticmethod
    def _verify_schema(database: sqlite3.Connection) -> str:
        try:
            row = database.execute(
                "SELECT value FROM compass_meta WHERE key='schema_version'"
            ).fetchone()
        except sqlite3.Error as exc:
            raise CompassError(
                "INVALID_STORAGE", "SQLite file is not a COMPASS-C notebook"
            ) from exc
        if row is None or row["value"] not in {"1", "2", SCHEMA_VERSION}:
            raise CompassError("UNSUPPORTED_SCHEMA", "Unsupported COMPASS-C notebook schema")
        expected = {
            "compass_meta": ("key", "value"),
            "decisions": (
                "id",
                "objective",
                "stakes",
                "constraints_json",
                "revision",
                "created_at",
            ),
            "notes": (
                "id",
                "decision_id",
                "kind",
                "content",
                "status",
                "source",
                "dependencies_json",
                "stale",
                "created_at",
            ),
            "invalidations": (
                "id",
                "decision_id",
                "root_id",
                "reason",
                "affected_json",
                "revision",
                "created_at",
            ),
        }
        if row["value"] in {"2", "3"}:
            expected["note_revisions"] = (
                "id",
                "decision_id",
                "supersedes",
                "note_id",
                "reason",
                "revision",
                "created_at",
            )
        if row["value"] == "3":
            expected["experiment_plans"] = (
                "id",
                "decision_id",
                "model_note_id",
                "parameters_json",
                "proposal_json",
                "revision",
                "created_at",
            )
            expected["experiment_observations"] = (
                "id",
                "decision_id",
                "plan_id",
                "event_id",
                "experiment_id",
                "observation_json",
                "update_json",
                "outcome_note_id",
                "model_note_id",
                "revision",
                "created_at",
            )
        for table, columns in expected.items():
            actual = database.execute(f"PRAGMA table_info({table})").fetchall()
            if tuple(column["name"] for column in actual) != columns:
                raise CompassError("INVALID_STORAGE", "Notebook tables do not match its schema")
            primary = "key" if table == "compass_meta" else "id"
            if [column["name"] for column in actual if column["pk"]] != [primary]:
                raise CompassError("INVALID_STORAGE", "Notebook table has no valid primary key")
            for column in actual:
                expected_type = "INTEGER" if column["name"] in {"revision", "stale"} else "TEXT"
                if column["type"].upper() != expected_type or (
                    column["name"] != primary and not column["notnull"]
                ):
                    raise CompassError(
                        "INVALID_STORAGE", "Notebook columns do not match its schema"
                    )
            foreign_keys = {
                (key["from"], key["table"], key["to"])
                for key in database.execute(f"PRAGMA foreign_key_list({table})")
            }
            required = (
                set()
                if table in {"compass_meta", "decisions"}
                else {("decision_id", "decisions", "id")}
            )
            if table == "note_revisions":
                required.update({("supersedes", "notes", "id"), ("note_id", "notes", "id")})
            if table == "experiment_plans":
                required.add(("model_note_id", "notes", "id"))
            if table == "experiment_observations":
                required.update(
                    {
                        ("plan_id", "experiment_plans", "id"),
                        ("outcome_note_id", "notes", "id"),
                        ("model_note_id", "notes", "id"),
                    }
                )
            if foreign_keys != required:
                raise CompassError(
                    "INVALID_STORAGE", "Notebook relationships do not match its schema"
                )
        if row["value"] == "3":
            unique_columns = set()
            for index in database.execute("PRAGMA index_list(experiment_observations)"):
                if not index["unique"] or index["partial"]:
                    continue
                # Table-valued PRAGMA binds an untrusted stored index name as data.
                columns = tuple(
                    item["name"]
                    for item in database.execute(
                        "SELECT name FROM pragma_index_info(?)", (index["name"],)
                    )
                )
                unique_columns.add(columns)
            if not {("decision_id", "event_id"), ("plan_id",)} <= unique_columns:
                raise CompassError(
                    "INVALID_STORAGE", "Experiment observation uniqueness is missing"
                )
        return row["value"]

    @staticmethod
    def _decision(database: sqlite3.Connection, decision_id: str) -> sqlite3.Row:
        identifier(decision_id, "decision_id")
        row = database.execute("SELECT * FROM decisions WHERE id=?", (decision_id,)).fetchone()
        if row is None:
            raise CompassError("NOT_FOUND", "Decision not found")
        Notebook._decode_decision(row)
        return row

    @staticmethod
    def _decode_decision(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        try:
            identifier(result["id"], "stored decision_id")
            text(result["objective"], "stored objective")
            text(result["created_at"], "stored created_at")
            integer(result["revision"], "stored revision", 1, 2**63 - 1)
            if result["stakes"] not in STAKES:
                raise CompassError("INVALID_STORAGE", "Invalid stored stakes")
            result["constraints"] = strings(
                json.loads(result.pop("constraints_json")), "constraints"
            )
        except (CompassError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise CompassError("INVALID_STORAGE", "Malformed stored decision") from exc
        result["decision_id"] = result.pop("id")
        return result

    @staticmethod
    def _revision(row: sqlite3.Row | dict[str, Any], expected: int) -> None:
        integer(expected, "expected_revision", 1)
        if row["revision"] != expected:
            raise CompassError(
                "REVISION_CONFLICT",
                f"Read the decision again; current revision is {row['revision']}",
            )

    def start(
        self,
        objective: str,
        stakes: str = "medium",
        constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        text(objective, "objective")
        text(stakes, "stakes", limit=20)
        if stakes not in STAKES:
            raise CompassError("INVALID_INPUT", "stakes must be low, medium, or high")
        parsed_constraints = strings([] if constraints is None else constraints, "constraints")
        decision_id = uuid.uuid4().hex
        with self._start_connection() as database:
            database.execute(
                "INSERT INTO decisions VALUES (?, ?, ?, ?, 1, ?)",
                (decision_id, objective, stakes, json.dumps(parsed_constraints), utc()),
            )
        return {
            "decision_id": decision_id,
            "revision": 1,
            "scope": "analysis_only",
            "action_permission": "not_granted",
            "next": "Record actual evidence and at least two alternatives; do not invent facts.",
        }

    def record(
        self,
        decision_id: str,
        expected_revision: int,
        kind: str,
        content: str,
        status: str = "proposed",
        source: str = "",
        depends_on: list[str] | None = None,
    ) -> dict[str, Any]:
        text(kind, "kind", limit=30)
        text(status, "status", limit=30)
        text(content, "content")
        text(source, "source", limit=4_000, empty=True)
        if kind not in KINDS or status not in STATUSES:
            raise CompassError("INVALID_INPUT", "Unknown note kind or evidence status")
        if status in {"observed", "computed"} and not source.strip():
            raise CompassError("SOURCE_REQUIRED", "Observed/computed notes need provenance")
        dependencies = strings([] if depends_on is None else depends_on, "depends_on")
        for dependency in dependencies:
            identifier(dependency, "dependency")
        if len(dependencies) != len(set(dependencies)):
            raise CompassError("INVALID_INPUT", "Duplicate dependencies")
        note_id = uuid.uuid4().hex
        with self._existing_connection(writable=True) as database:
            row = self._snapshot(database, decision_id)
            self._revision(row, expected_revision)
            count = database.execute(
                "SELECT COUNT(*) FROM notes WHERE decision_id=?", (decision_id,)
            ).fetchone()[0]
            if count >= 2_000:
                raise CompassError("CAPACITY", "Decision note limit reached")
            for dependency in dependencies:
                found = database.execute(
                    "SELECT decision_id, stale FROM notes WHERE id=?", (dependency,)
                ).fetchone()
                if found is None or found["decision_id"] != decision_id:
                    raise CompassError("INVALID_DEPENDENCY", "Dependency belongs elsewhere")
                if found["stale"]:
                    raise CompassError("STALE_DEPENDENCY", "Cannot build on invalidated evidence")
            database.execute(
                "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (
                    note_id,
                    decision_id,
                    kind,
                    content,
                    status,
                    source,
                    json.dumps(dependencies),
                    utc(),
                ),
            )
            database.execute("UPDATE decisions SET revision=revision+1 WHERE id=?", (decision_id,))
        return {
            "decision_id": decision_id,
            "note_id": note_id,
            "revision": expected_revision + 1,
            "action_permission": "not_granted",
            "source_verified": False,
        }

    def get(self, decision_id: str) -> dict[str, Any]:
        with self._existing_connection(writable=False) as database:
            return self._snapshot(database, decision_id)

    @staticmethod
    def _snapshot(database: sqlite3.Connection, decision_id: str) -> dict[str, Any]:
        row = Notebook._decode_decision(Notebook._decision(database, decision_id))
        notes = [
            dict(note)
            for note in database.execute(
                "SELECT * FROM notes WHERE decision_id=? ORDER BY rowid", (decision_id,)
            )
        ]
        invalidations = [
            dict(item)
            for item in database.execute(
                "SELECT * FROM invalidations WHERE decision_id=? ORDER BY rowid", (decision_id,)
            )
        ]
        version = database.execute(
            "SELECT value FROM compass_meta WHERE key='schema_version'"
        ).fetchone()[0]
        revisions = (
            []
            if version == "1"
            else [
                dict(item)
                for item in database.execute(
                    "SELECT * FROM note_revisions WHERE decision_id=? ORDER BY rowid",
                    (decision_id,),
                )
            ]
        )
        try:
            known: dict[str, dict[str, Any]] = {}
            for note in notes:
                identifier(note["id"], "stored note_id")
                text(note["content"], "stored content")
                text(note["source"], "stored source", limit=4_000, empty=True)
                text(note["created_at"], "stored created_at")
                if note["kind"] not in KINDS or note["status"] not in STATUSES:
                    raise ValueError("Unknown stored note type")
                if note["status"] in {"observed", "computed"} and not note["source"].strip():
                    raise ValueError("Missing stored provenance")
                if note["stale"] not in (0, 1):
                    raise ValueError("Invalid stored staleness")
                deps = strings(json.loads(note.pop("dependencies_json")), "stored dependencies")
                if len(deps) != len(set(deps)) or any(dep not in known for dep in deps):
                    raise ValueError("Invalid stored dependency graph")
                if not note["stale"] and any(known[dep]["stale"] for dep in deps):
                    raise ValueError("Current note relies on stale evidence")
                note["depends_on"] = deps
                note["stale"] = bool(note["stale"])
                known[note["id"]] = note
            for invalidation in invalidations:
                identifier(invalidation["id"], "stored invalidation_id")
                text(invalidation["reason"], "stored reason")
                text(invalidation["created_at"], "stored created_at")
                integer(invalidation["revision"], "stored revision", 2, row["revision"])
                affected = strings(
                    json.loads(invalidation.pop("affected_json")),
                    "stored affected notes",
                    maximum=2_000,
                )
                if (
                    invalidation["root_id"] not in known
                    or invalidation["root_id"] not in affected
                    or len(affected) != len(set(affected))
                    or any(
                        note_id not in known or not known[note_id]["stale"] for note_id in affected
                    )
                ):
                    raise ValueError("Invalid stored invalidation")
                invalidation["affected_notes"] = affected
            replaced: set[str] = set()
            replacements: set[str] = set()
            note_order = {note_id: index for index, note_id in enumerate(known)}
            for revision in revisions:
                identifier(revision["id"], "stored revision_id")
                text(revision["reason"], "stored reason")
                text(revision["created_at"], "stored created_at")
                integer(revision["revision"], "stored revision", 2, row["revision"])
                prior = known.get(revision["supersedes"])
                replacement = known.get(revision["note_id"])
                if (
                    prior is None
                    or replacement is None
                    or not prior["stale"]
                    or prior["id"] == replacement["id"]
                    or prior["kind"] != replacement["kind"]
                    or prior["id"] in replaced
                    or replacement["id"] in replacements
                    or note_order[prior["id"]] >= note_order[replacement["id"]]
                ):
                    raise ValueError("Invalid stored revision history")
                matches = [
                    item
                    for item in invalidations
                    if (
                        item["root_id"] == revision["supersedes"]
                        and item["revision"] == revision["revision"]
                        and item["reason"] == revision["reason"]
                    )
                ]
                if len(matches) != 1:
                    raise ValueError("Stored replacement has no matching invalidation")
                replaced.add(prior["id"])
                replacements.add(replacement["id"])
        except (CompassError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise CompassError("INVALID_STORAGE", "Malformed stored decision history") from exc
        row.update(
            notes=notes,
            invalidations=invalidations,
            revisions=revisions,
            scope="analysis_only",
            action_permission="not_granted",
        )
        return row

    def invalidate(
        self,
        decision_id: str,
        expected_revision: int,
        note_id: str,
        reason: str,
    ) -> dict[str, Any]:
        identifier(note_id, "note_id")
        text(reason, "reason")
        with self._existing_connection(writable=True) as database:
            row = self._snapshot(database, decision_id)
            self._revision(row, expected_revision)
            affected = self._affected(row["notes"], note_id)
            self._write_invalidation(
                database, decision_id, expected_revision + 1, note_id, reason, affected
            )
        return {
            "decision_id": decision_id,
            "revision": expected_revision + 1,
            "invalidated": sorted(affected),
            "action_permission": "not_granted",
        }

    @staticmethod
    def _affected(notes: list[dict[str, Any]], note_id: str) -> set[str]:
        if note_id not in {note["id"] for note in notes}:
            raise CompassError("NOT_FOUND", "Note not found in this decision")
        affected = {note_id} | {note["id"] for note in notes if note["kind"] == "decision"}
        changed = True
        while changed:
            before = len(affected)
            for note in notes:
                if affected.intersection(note["depends_on"]):
                    affected.add(note["id"])
            changed = len(affected) > before
        return affected

    @staticmethod
    def _write_invalidation(
        database: sqlite3.Connection,
        decision_id: str,
        revision: int,
        note_id: str,
        reason: str,
        affected: set[str],
    ) -> None:
        database.executemany(
            "UPDATE notes SET stale=1 WHERE id=?", [(value,) for value in sorted(affected)]
        )
        database.execute("UPDATE decisions SET revision=? WHERE id=?", (revision, decision_id))
        database.execute(
            "INSERT INTO invalidations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                decision_id,
                note_id,
                reason,
                json.dumps(sorted(affected)),
                revision,
                utc(),
            ),
        )

    def revise(
        self,
        decision_id: str,
        expected_revision: int,
        note_id: str,
        content: str,
        reason: str,
        status: str = "proposed",
        source: str = "",
        depends_on: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append a replacement and invalidate old reasoning in one explicit update.

        Omitted dependencies inherit the original links. An explicit empty list
        removes those links; neither form can reuse stale or affected evidence.
        """
        identifier(note_id, "note_id")
        text(content, "content")
        text(reason, "reason")
        text(status, "status", limit=30)
        text(source, "source", limit=4_000, empty=True)
        if status not in STATUSES:
            raise CompassError("INVALID_INPUT", "Unknown evidence status")
        if status in {"observed", "computed"} and not source.strip():
            raise CompassError("SOURCE_REQUIRED", "Observed/computed notes need provenance")
        if depends_on is not None:
            strings(depends_on, "depends_on")
        replacement_id = uuid.uuid4().hex
        with self._existing_connection(writable=True) as database:
            row = self._snapshot(database, decision_id)
            self._revision(row, expected_revision)
            if self._verify_schema(database) not in {"2", "3"}:
                raise CompassError("MIGRATION_REQUIRED", "Run migrate explicitly before revising")
            notes = {note["id"]: note for note in row["notes"]}
            if note_id not in notes:
                raise CompassError("NOT_FOUND", "Note not found in this decision")
            if any(item["supersedes"] == note_id for item in row["revisions"]):
                raise CompassError("NOTE_SUPERSEDED", "Revise the replacement note instead")
            if len(notes) >= 2_000:
                raise CompassError("CAPACITY", "Decision note limit reached")
            old = notes[note_id]
            dependencies = old["depends_on"] if depends_on is None else depends_on
            for dependency in dependencies:
                identifier(dependency, "dependency")
            if len(dependencies) != len(set(dependencies)):
                raise CompassError("INVALID_INPUT", "Duplicate dependencies")
            affected = self._affected(row["notes"], note_id)
            for dependency in dependencies:
                if dependency not in notes:
                    raise CompassError("INVALID_DEPENDENCY", "Dependency belongs elsewhere")
                if notes[dependency]["stale"] or dependency in affected:
                    raise CompassError("STALE_DEPENDENCY", "Cannot build on invalidated evidence")
            self._write_invalidation(
                database, decision_id, expected_revision + 1, note_id, reason, affected
            )
            timestamp = utc()
            database.execute(
                "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (
                    replacement_id,
                    decision_id,
                    old["kind"],
                    content,
                    status,
                    source,
                    json.dumps(dependencies),
                    timestamp,
                ),
            )
            database.execute(
                "INSERT INTO note_revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    decision_id,
                    note_id,
                    replacement_id,
                    reason,
                    expected_revision + 1,
                    timestamp,
                ),
            )
        return {
            "decision_id": decision_id,
            "note_id": replacement_id,
            "supersedes": note_id,
            "revision": expected_revision + 1,
            "invalidated": sorted(affected),
            "action_permission": "not_granted",
            "source_verified": False,
        }

    def migrate(self) -> dict[str, Any]:
        """Explicit, transactional schema-1/2 upgrade; reads never call this method."""
        with self._existing_connection(writable=True) as database:
            version = self._verify_schema(database)
            for row in database.execute("SELECT id FROM decisions"):
                self._snapshot(database, row["id"])
            if database.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise CompassError("INVALID_STORAGE", "Notebook contains orphaned history")
            migrated = version != SCHEMA_VERSION
            if migrated:
                if version == "1":
                    self._revision_schema(database)
                self._experiment_schema(database)
                database.execute(
                    "UPDATE compass_meta SET value=? WHERE key='schema_version'", (SCHEMA_VERSION,)
                )
                self._verify_schema(database)
        return {
            "from_version": version,
            "schema_version": SCHEMA_VERSION,
            "migrated": migrated,
            "scope": "analysis_only",
            "action_permission": "not_granted",
        }

    def list(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List recent decision summaries from one read-only snapshot."""
        integer(limit, "limit", 1, 100)
        integer(offset, "offset", 0)
        with self._existing_connection(writable=False) as database:
            total = database.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            decisions = [
                self._decode_decision(row)
                for row in database.execute(
                    "SELECT * FROM decisions ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]
        return {
            "decisions": decisions,
            "total": total,
            "limit": limit,
            "offset": offset,
            "scope": "analysis_only",
            "action_permission": "not_granted",
        }

    def brief(self, decision_id: str) -> dict[str, Any]:
        """Render exact recorded claims, with current reasoning and stale history separated.

        The brief adds an explicit reversal-condition coverage check to the
        backwards-compatible review contract. It never interprets the condition,
        verifies a source, or invents a recommendation.
        """
        decision = self.get(decision_id)
        current = [note for note in decision["notes"] if not note["stale"]]
        sections = {
            "recommendations": {"decision"},
            "alternatives": {"alternative"},
            "evidence": {"evidence"},
            "uncertainty": {"assumption", "limitation", "forecast"},
            "checks": {"test"},
            "effects": {"effect"},
            "outcomes": {"outcome"},
            "reversal_conditions": {"reversal_condition"},
        }
        result = {key: value for key, value in decision.items() if key != "notes"}
        result.update(
            {
                name: [note for note in current if note["kind"] in kinds]
                for name, kinds in sections.items()
            }
        )
        result["stale_notes"] = [note for note in decision["notes"] if note["stale"]]
        review = self._review_snapshot(decision)
        if not result["reversal_conditions"]:
            review["next_checks"].append(
                "Record an explicit reversal condition for reconsideration."
            )
            review["status"] = "needs_work"
        result["review"] = review
        result["source_verified"] = False
        return result

    def review(self, decision_id: str) -> dict[str, Any]:
        return self._review_snapshot(self.get(decision_id))

    @staticmethod
    def _review_snapshot(decision: dict[str, Any]) -> dict[str, Any]:
        current = [note for note in decision["notes"] if not note["stale"]]
        counts = {kind: sum(note["kind"] == kind for note in current) for kind in sorted(KINDS)}
        missing: list[str] = []
        if counts["evidence"] == 0:
            missing.append("Record decision-relevant evidence with uncertainty and provenance.")
        if counts["alternative"] < 2:
            missing.append("Compare at least two alternatives, including delay or inaction.")
        if counts["test"] == 0:
            missing.append("Specify a check that could change the conclusion.")
        if counts["limitation"] == 0:
            missing.append("State the operating envelope and remaining uncertainty.")
        if counts["decision"] == 0:
            missing.append("Record a conditional recommendation; this cannot authorize execution.")
        if decision["stakes"] == "high":
            if not decision["constraints"]:
                missing.append("Specify constraints and the actual authority for any action.")
            if counts["effect"] == 0:
                missing.append("Trace higher-order effects, reflexivity, and recovery feasibility.")
        stale = [note["id"] for note in decision["notes"] if note["stale"]]
        ungrounded = [
            note["id"]
            for note in current
            if note["kind"] == "evidence" and note["status"] in {"assumed", "proposed"}
        ]
        if ungrounded:
            missing.append("Some evidence entries are only assumptions or proposals; support them.")
        return {
            "decision_id": decision["decision_id"],
            "revision": decision["revision"],
            "current_counts": counts,
            "status": "needs_work" if missing else "record_complete_not_verified",
            "next_checks": missing,
            "stale_notes": stale,
            "action_permission": "not_granted",
            "source_verified": False,
            "limits": (
                "Structural checks only; note presence does not establish truth or authority."
            ),
        }

"""Machine-readable COMPASS-C CLI with no network or external execution."""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import VERSION, CompassError, Notebook, calculate
from .calculations import CALCULATIONS
from .core import KINDS, STATUSES
from .evaluation import evaluate
from .evidence import apply_updates, preview_updates
from .lifecycle import (
    apply_observation,
    experiment,
    experiments,
    lifecycle_view,
    plan_experiment,
    preview_observation,
)


class JsonArgumentParser(argparse.ArgumentParser):
    """Turn argparse failures into the CLI's stable error envelope."""

    def error(self, message: str) -> None:
        raise CompassError("INVALID_ARGUMENTS", message)


def parse_json(raw: str, *, limit: int = 100_000) -> Any:
    if len(raw) > limit:
        raise CompassError("INPUT_TOO_LARGE", f"JSON input exceeds {limit} characters")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CompassError("INVALID_JSON", "Duplicate JSON keys are not allowed")
            result[key] = value
        return result

    def no_constants(_value: str) -> None:
        raise CompassError("INVALID_JSON", "Non-finite JSON numbers are not allowed")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise CompassError("INVALID_JSON", "Non-finite JSON numbers are not allowed")
        return number

    try:
        return json.loads(
            raw,
            object_pairs_hook=no_duplicates,
            parse_constant=no_constants,
            parse_float=finite_float,
        )
    except CompassError:
        raise
    except (ValueError, RecursionError) as exc:
        raise CompassError("INVALID_JSON", "Invalid JSON input") from exc


def read_json(path: str) -> Any:
    """Read a bounded UTF-8 input file without exposing paths or file contents in errors."""
    try:
        with Path(path).open("r", encoding="utf-8") as source:
            raw = source.read(1_000_001)
    except (OSError, UnicodeError, ValueError) as exc:
        raise CompassError("INPUT_FILE_ERROR", "Cannot read a UTF-8 JSON input file") from exc
    return parse_json(raw, limit=1_000_000)


def parser() -> JsonArgumentParser:
    root = JsonArgumentParser(
        description="COMPASS-C: local advisory decision records and bounded calculations"
    )
    root.add_argument("--version", action="version", version=VERSION)
    root.add_argument(
        "--db",
        default=os.environ.get("COMPASS_DB", str(Path.cwd() / ".compass" / "decisions.sqlite3")),
        help="workspace-owned SQLite notebook; not a security or authorization boundary",
    )
    commands = root.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    start = commands.add_parser("start", help="create a task-owned decision notebook entry")
    start.add_argument("--objective", required=True)
    start.add_argument("--stakes", choices=["low", "medium", "high"], default="medium")
    start.add_argument("--constraints", default="[]", help="JSON list")

    for name in ("get", "review", "brief"):
        command = commands.add_parser(name)
        command.add_argument("decision_id")

    listing = commands.add_parser(
        "list", help="discover decisions and reconcile a lost start response"
    )
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--offset", type=int, default=0)
    commands.add_parser("migrate", help="explicitly upgrade an existing notebook schema")

    record = commands.add_parser("record")
    record.add_argument("decision_id")
    record.add_argument("--revision", required=True, type=int)
    record.add_argument("--kind", required=True, help="note kind: " + ", ".join(sorted(KINDS)))
    record.add_argument("--content", required=True)
    status_help = "source status: " + ", ".join(sorted(STATUSES)) + " (default: proposed)"
    record.add_argument("--status", default="proposed", help=status_help)
    record.add_argument("--source", default="")
    record.add_argument("--depends-on", default="[]", help="JSON list of note IDs")

    invalidate = commands.add_parser("invalidate")
    invalidate.add_argument("decision_id")
    invalidate.add_argument("note_id")
    invalidate.add_argument("--revision", required=True, type=int)
    invalidate.add_argument("--reason", required=True)

    revise = commands.add_parser(
        "revise", help="replace a note and invalidate dependent conclusions"
    )
    revise.add_argument("decision_id")
    revise.add_argument("note_id")
    revise.add_argument("--revision", required=True, type=int)
    revise.add_argument("--content", required=True)
    revise.add_argument("--reason", required=True)
    revise.add_argument("--status", default="proposed", help=status_help)
    revise.add_argument("--source", default="")
    revise.add_argument(
        "--depends-on", default=None, help="JSON note IDs; omission retains prior links"
    )

    updates = commands.add_parser(
        "update-evidence", help="preview a sourced evidence batch; --apply explicitly commits it"
    )
    updates.add_argument("decision_id")
    updates.add_argument("--revision", required=True, type=int)
    updates.add_argument("--updates", required=True, help="JSON list of sourced replacements")
    updates.add_argument(
        "--apply", action="store_true", help="commit the validated batch atomically"
    )

    plan = commands.add_parser(
        "plan-experiment", help="freeze a bounded experiment against the current decision revision"
    )
    plan.add_argument("decision_id")
    plan.add_argument("--revision", required=True, type=int)
    plan.add_argument(
        "--parameters-file", required=True, help="bounded UTF-8 model and experiment JSON"
    )
    plan.add_argument("--depends-on", default="[]", help="JSON list of current source note IDs")
    plan.add_argument(
        "--full", action="store_true", help="include the frozen model and full proposal"
    )

    plans = commands.add_parser("experiments", help="discover a decision's saved experiment plans")
    plans.add_argument("decision_id")
    resume = commands.add_parser("experiment", help="resume a saved experiment and its next step")
    resume.add_argument("plan_id")
    resume.add_argument(
        "--full", action="store_true", help="include frozen inputs and observation history"
    )

    observe = commands.add_parser(
        "observe-experiment", help="preview a sourced observation; --apply explicitly records it"
    )
    observe.add_argument("plan_id")
    observe.add_argument("--revision", required=True, type=int)
    observe.add_argument("--experiment", required=True, help="experiment ID in the saved proposal")
    observe.add_argument(
        "--event-id", required=True, help="stable observation identity within this decision"
    )
    observe.add_argument(
        "--observation-file", required=True, help="bounded UTF-8 sourced observation JSON"
    )
    observe.add_argument(
        "--apply",
        action="store_true",
        help="record the event once and invalidate affected reasoning",
    )
    observe.add_argument(
        "--full",
        action="store_true",
        help="include prior and posterior models and the supplied observation",
    )

    calculation = commands.add_parser("calculate")
    calculation.add_argument(
        "kind",
        choices=CALCULATIONS,
    )
    calculation.add_argument("--parameters", required=True, help="JSON object")
    evaluation = commands.add_parser(
        "evaluate", help="report frozen paired host evaluation results"
    )
    evaluation.add_argument("--corpus", required=True, help="frozen corpus JSON file")
    evaluation.add_argument("--results", required=True, help="paired observations JSON file")
    return root


def execute(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.command == "calculate":
        return calculate(arguments.kind, parse_json(arguments.parameters))
    if arguments.command == "evaluate":
        return evaluate(read_json(arguments.corpus), read_json(arguments.results))

    notebook = Notebook(arguments.db)
    if arguments.command == "plan-experiment":
        return lifecycle_view(
            plan_experiment(
                notebook,
                arguments.decision_id,
                arguments.revision,
                read_json(arguments.parameters_file),
                parse_json(arguments.depends_on),
            ),
            arguments.full,
        )
    if arguments.command == "experiment":
        return lifecycle_view(experiment(notebook, arguments.plan_id), arguments.full)
    if arguments.command == "experiments":
        return experiments(notebook, arguments.decision_id)
    if arguments.command == "observe-experiment":
        operation = apply_observation if arguments.apply else preview_observation
        return lifecycle_view(
            operation(
                notebook,
                arguments.plan_id,
                arguments.revision,
                arguments.experiment,
                arguments.event_id,
                read_json(arguments.observation_file),
            ),
            arguments.full,
        )
    if arguments.command == "update-evidence":
        operation = apply_updates if arguments.apply else preview_updates
        return operation(
            notebook, arguments.decision_id, arguments.revision, parse_json(arguments.updates)
        )
    if arguments.command == "start":
        return notebook.start(
            arguments.objective, arguments.stakes, parse_json(arguments.constraints)
        )
    if arguments.command == "get":
        return notebook.get(arguments.decision_id)
    if arguments.command == "review":
        return notebook.review(arguments.decision_id)
    if arguments.command == "brief":
        return notebook.brief(arguments.decision_id)
    if arguments.command == "list":
        return notebook.list(arguments.limit, arguments.offset)
    if arguments.command == "migrate":
        return notebook.migrate()
    if arguments.command == "revise":
        return notebook.revise(
            arguments.decision_id,
            arguments.revision,
            arguments.note_id,
            arguments.content,
            arguments.reason,
            arguments.status,
            arguments.source,
            parse_json(arguments.depends_on) if arguments.depends_on is not None else None,
        )
    if arguments.command == "record":
        return notebook.record(
            arguments.decision_id,
            arguments.revision,
            arguments.kind,
            arguments.content,
            arguments.status,
            arguments.source,
            parse_json(arguments.depends_on),
        )
    return notebook.invalidate(
        arguments.decision_id,
        arguments.revision,
        arguments.note_id,
        arguments.reason,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = execute(parser().parse_args(argv))
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, indent=2))
        return 0
    except CompassError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc)}}))
        return 2
    except (sqlite3.Error, OSError):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "STORAGE_ERROR",
                        "message": (
                            "Local storage unavailable; inspect permissions and configuration."
                        ),
                    },
                }
            )
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())

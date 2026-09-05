"""Machine-readable COMPASS-C CLI with no network or external execution."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import VERSION, CompassError, Notebook, calculate


class JsonArgumentParser(argparse.ArgumentParser):
    """Turn argparse failures into the CLI's stable error envelope."""

    def error(self, message: str) -> None:
        raise CompassError("INVALID_ARGUMENTS", message)


def parse_json(raw: str) -> Any:
    if len(raw) > 100_000:
        raise CompassError("INPUT_TOO_LARGE", "JSON input exceeds 100000 characters")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CompassError("INVALID_JSON", "Duplicate JSON keys are not allowed")
            result[key] = value
        return result

    def no_constants(_value: str) -> None:
        raise CompassError("INVALID_JSON", "Non-finite JSON numbers are not allowed")

    try:
        return json.loads(raw, object_pairs_hook=no_duplicates, parse_constant=no_constants)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise CompassError("INVALID_JSON", "Invalid JSON input") from exc


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

    start = commands.add_parser("start")
    start.add_argument("--objective", required=True)
    start.add_argument("--stakes", choices=["low", "medium", "high"], default="medium")
    start.add_argument("--constraints", default="[]", help="JSON list")

    for name in ("get", "review"):
        command = commands.add_parser(name)
        command.add_argument("decision_id")

    record = commands.add_parser("record")
    record.add_argument("decision_id")
    record.add_argument("--revision", required=True, type=int)
    record.add_argument("--kind", required=True)
    record.add_argument("--content", required=True)
    record.add_argument("--status", default="proposed")
    record.add_argument("--source", default="")
    record.add_argument("--depends-on", default="[]", help="JSON list of note IDs")

    invalidate = commands.add_parser("invalidate")
    invalidate.add_argument("decision_id")
    invalidate.add_argument("note_id")
    invalidate.add_argument("--revision", required=True, type=int)
    invalidate.add_argument("--reason", required=True)

    calculation = commands.add_parser("calculate")
    calculation.add_argument(
        "kind", choices=["compare", "committee", "bundle", "feedback", "recovery", "tail", "brier"]
    )
    calculation.add_argument("--parameters", required=True, help="JSON object")
    return root


def execute(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.command == "calculate":
        return calculate(arguments.kind, parse_json(arguments.parameters))

    notebook = Notebook(arguments.db)
    if arguments.command == "start":
        return notebook.start(
            arguments.objective, arguments.stakes, parse_json(arguments.constraints)
        )
    if arguments.command == "get":
        return notebook.get(arguments.decision_id)
    if arguments.command == "review":
        return notebook.review(arguments.decision_id)
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

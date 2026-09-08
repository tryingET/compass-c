"""Capture bounded dogfood subprocesses and guidance reads without changing product outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "run-2"


def retain(record):
    RUN.mkdir(exist_ok=True)
    record["capture_driver_process"] = {
        "executable": sys.executable,
        "exposed_argv": sys.argv,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
    }
    with (RUN / "trace.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def output_path(phase, name):
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Output must be one filename")
    directory = RUN / phase
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def save(phase, name, value):
    with output_path(phase, name).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run(phase, kind, argv, *, output=None, timeout=30):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = datetime.now(UTC).isoformat()
    clock = time.monotonic()
    record = {
        "phase": phase,
        "operation": "subprocess",
        "kind": kind,
        "argv": argv,
        "started_at": started,
        "timeout_seconds": timeout,
        "environment_controls": {"PYTHONPATH": "removed", "PYTHONDONTWRITEBYTECODE": "1"},
    }
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, env=environment, timeout=timeout, check=False
        )
        record.update(
            exit_status=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        record.update(
            exit_status=None,
            stdout=stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout,
            stderr=stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else stderr,
            timed_out=True,
        )
    except OSError as exc:
        record.update(
            exit_status=None,
            stdout="",
            stderr=str(exc),
            timed_out=False,
            launch_error=type(exc).__name__,
        )
    record["finished_at"] = datetime.now(UTC).isoformat()
    record["elapsed_seconds"] = time.monotonic() - clock
    record["stdout_utf8_bytes"] = len(record["stdout"].encode("utf-8"))
    record["stderr_utf8_bytes"] = len(record["stderr"].encode("utf-8"))
    retain(record)
    if output:
        save(phase, output, record)
    return record


def read(phase, path):
    content = Path(path).read_bytes()
    decoded = content.decode("utf-8")
    retain(
        {
            "phase": phase,
            "operation": "read",
            "path": str(Path(path).absolute()),
            "sha256": hashlib.sha256(content).hexdigest(),
            "utf8_bytes": len(content),
            "observed_at": datetime.now(UTC).isoformat(),
        }
    )
    return decoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["prepare", "resume", "review"], required=True)
    commands = parser.add_subparsers(dest="operation", required=True)
    reading = commands.add_parser("read")
    reading.add_argument("path")
    execution = commands.add_parser("run")
    execution.add_argument(
        "--kind", choices=["setup", "help", "product", "experiment", "verification"], required=True
    )
    execution.add_argument("--output")
    execution.add_argument("--timeout", type=int, default=30)
    execution.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.operation == "read":
        print(read(args.phase, args.path))
        return 0
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    if not argv:
        parser.error("Provide the exact target argv after --")
    if not 1 <= args.timeout <= 60:
        parser.error("Timeout must be between 1 and 60 seconds")
    record = run(args.phase, args.kind, argv, output=args.output, timeout=args.timeout)
    sys.stdout.write(record["stdout"])
    sys.stderr.write(record["stderr"])
    return record["exit_status"] if record["exit_status"] is not None else 124


if __name__ == "__main__":
    raise SystemExit(main())

"""BDD for capture ergonomics, independent of product outcome and participant behavior."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "evals" / "dogfood" / "v4-lifecycle"


@pytest.fixture
def capture(tmp_path, monkeypatch):
    # Before the new helper exists, exercise its frozen predecessor to demonstrate RED.
    source = CAPTURES / "capture-run-3.py"
    if not source.exists():
        source = CAPTURES / "capture-run-2.py"
    spec = importlib.util.spec_from_file_location("capture_under_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.RUN = tmp_path / "run-3"
    module.RUN.mkdir()
    (module.RUN / "manifest.json").write_text(
        json.dumps({"installed_cli": sys.executable, "installed_python": sys.executable}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(tmp_path / "no-path-fallback"))
    return module


def trace(capture):
    return [json.loads(line) for line in (capture.RUN / "trace.jsonl").read_text().splitlines()]


@pytest.mark.parametrize(
    "alias,key", [("compass-c", "installed_cli"), ("installed-python", "installed_python")]
)
def test_exact_alias_uses_frozen_target_and_preserves_all_arguments(capture, alias, key):
    arguments = ["space separated", '{"literal": "$(unchanged)"}', "compass-c", "installed-python"]
    requested = [alias, "-I", "-c", "import json,sys; print(json.dumps(sys.argv[1:]))", *arguments]
    original = requested.copy()
    record = capture.run("prepare", "product", requested, output="result.json")
    assert record["exit_status"] == 0, record
    assert requested == original
    assert record["requested_argv"] == requested
    assert record["argv"] == [sys.executable, *requested[1:]]
    assert record["cwd"] == str(Path.cwd())
    assert json.loads(record["stdout"]) == arguments
    assert record["stderr"] == ""
    assert record["target_resolution"] == {
        "alias": alias,
        "manifest_key": key,
        "manifest_sha256": hashlib.sha256((capture.RUN / "manifest.json").read_bytes()).hexdigest(),
    }
    assert record["environment_controls"]["PYTHONPATH"] == "removed"
    assert record["stdout_utf8_bytes"] == len(record["stdout"].encode("utf-8"))
    assert trace(capture) == [record]
    assert json.loads((capture.RUN / "prepare" / "result.json").read_text()) == record


def test_unknown_path_is_not_repaired_or_retried(capture):
    requested = [str(capture.ROOT / "mistyped-path" / "compass-c"), "--version"]
    record = capture.run("prepare", "product", requested)
    assert record["exit_status"] is None
    assert record["launch_error"] == "FileNotFoundError"
    assert record["argv"] == record["requested_argv"] == requested
    assert record["target_resolution"] is None
    assert record["timed_out"] is False
    assert trace(capture) == [record]


def test_explicit_target_needs_no_manifest_and_preserves_child_failure(capture):
    (capture.RUN / "manifest.json").unlink()
    requested = [
        sys.executable,
        "-I",
        "-c",
        "import sys; print('visible stdout'); "
        "print('visible stderr', file=sys.stderr); sys.exit(7)",
    ]
    record = capture.run("resume", "experiment", requested)
    assert record["argv"] == record["requested_argv"] == requested
    assert record["target_resolution"] is None
    assert record["exit_status"] == 7
    assert record["stdout"] == "visible stdout\n"
    assert record["stderr"] == "visible stderr\n"
    assert record["kind"] == "experiment"
    assert record["elapsed_seconds"] >= 0
    assert trace(capture) == [record]


@pytest.mark.parametrize(
    "manifest",
    [None, "{", "{}", '{"installed_cli":"relative/path"}', '{"installed_cli":7}'],
    ids=["missing", "malformed", "missing-key", "relative-target", "nonstring-target"],
)
def test_alias_resolution_failure_is_retained_without_launch_or_fallback(
    capture, monkeypatch, manifest
):
    path = capture.RUN / "manifest.json"
    if manifest is None:
        path.unlink()
    else:
        path.write_text(manifest, encoding="utf-8")
    launched = []

    def unexpected_launch(*args, **kwargs):
        launched.append((args, kwargs))
        raise AssertionError("A broken frozen target must not launch any process")

    monkeypatch.setattr(capture.subprocess, "run", unexpected_launch)
    record = capture.run("prepare", "product", ["compass-c", "--version"])
    assert launched == []
    assert record["requested_argv"] == ["compass-c", "--version"]
    assert record["argv"] is None
    assert record["target_resolution"] is None
    assert record["resolution_error"] is True
    assert record["launch_error"]
    assert record["exit_status"] is None
    assert record["timed_out"] is False
    assert trace(capture) == [record]


def test_timeout_preserves_partial_output_and_one_attempt(capture, monkeypatch):
    launches = []

    def timeout(argv, **kwargs):
        launches.append((argv, kwargs))
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=b"\xc3\xa9", stderr=b"late")

    monkeypatch.setattr(capture.subprocess, "run", timeout)
    record = capture.run("resume", "experiment", ["installed-python", "-I", "check.py"], timeout=2)
    assert len(launches) == 1
    assert launches[0][0] == [sys.executable, "-I", "check.py"]
    assert record["requested_argv"] == ["installed-python", "-I", "check.py"]
    assert record["timed_out"] is True
    assert record["exit_status"] is None
    assert record["stdout"] == "é"
    assert record["stdout_utf8_bytes"] == 2
    assert record["stderr_utf8_bytes"] == 4
    assert record["timeout_seconds"] == 2
    assert trace(capture) == [record]


def test_reused_output_name_preserves_both_attempts_and_the_first_file(capture):
    first = capture.run("prepare", "help", ["installed-python", "--version"], output="same.json")
    original = (capture.RUN / "prepare" / "same.json").read_bytes()
    with pytest.raises(FileExistsError):
        capture.run("prepare", "help", ["installed-python", "--version"], output="same.json")
    attempts = trace(capture)
    assert len(attempts) == 2
    assert attempts[0] == first
    assert all(row["exit_status"] == 0 for row in attempts)
    assert (capture.RUN / "prepare" / "same.json").read_bytes() == original

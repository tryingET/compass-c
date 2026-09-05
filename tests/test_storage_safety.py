from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from compass_c import CompassError, Notebook, calculate


def test_construction_and_read_do_not_create_storage(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "decisions.sqlite3"
    notebook = Notebook(path)
    assert not path.exists()
    with pytest.raises(CompassError, match="does not exist") as error:
        notebook.get("a" * 32)
    assert error.value.code == "STORAGE_NOT_FOUND"
    assert not path.exists()
    assert not path.parent.exists()


def test_calculation_does_not_create_default_notebook(tmp_path: Path) -> None:
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "compass_c",
            "calculate",
            "brier",
            "--parameters",
            '{"probabilities":[0.8],"outcomes":[1]}',
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["ok"] is True
    assert not (tmp_path / ".compass").exists()


def test_malformed_start_does_not_create_storage(tmp_path: Path) -> None:
    path = tmp_path / "decisions.sqlite3"
    with pytest.raises(CompassError):
        Notebook(path).start("", "medium", [])
    assert not path.exists()


def test_read_does_not_initialize_unrelated_sqlite_file(tmp_path: Path) -> None:
    path = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE unrelated (value TEXT)")
    before = path.read_bytes()
    with pytest.raises(CompassError) as error:
        Notebook(path).get("a" * 32)
    assert error.value.code == "INVALID_STORAGE"
    assert path.read_bytes() == before


def test_start_refuses_unrelated_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite3"
    path.touch()
    with pytest.raises(CompassError):
        Notebook(path).start("Choose safely")
    assert path.read_bytes() == b""


def test_number_rejects_huge_integer_without_overflow() -> None:
    with pytest.raises(CompassError):
        calculate("feedback", {"a": 10**10_000, "gain": 0.5, "delay": 1})

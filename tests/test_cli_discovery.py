"""Regression for an actual installed-client dogfood discovery failure."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("portable", [False, True])
@pytest.mark.parametrize("command", ["record", "revise"])
def test_note_help_exposes_allowed_statuses_and_default_without_storage(
    tmp_path, portable, command
):
    db = tmp_path / "absent.sqlite3"
    entry = [str(ROOT / "skills/compass/scripts/compass.py")] if portable else ["-m", "compass_c"]
    process = subprocess.run(
        [sys.executable, "-I", *entry, "--db", str(db), command, "--help"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert process.returncode == 0, process.stderr
    help_text = " ".join(process.stdout.split())
    for status in ("assumed", "observed", "computed", "inferred", "proposed"):
        assert status in help_text
    assert "default: proposed" in help_text
    if command == "record":
        for kind in ("evidence", "alternative", "decision", "outcome", "reversal_condition"):
            assert kind in help_text
    assert not db.exists()

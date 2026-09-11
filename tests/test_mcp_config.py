"""Configuration checks independent of the optional MCP SDK."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_configuration_preserves_venv_interpreter_and_has_no_storage_effect(tmp_path):
    db = tmp_path / "absent directory" / "decisions.sqlite3"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/configure_mcp.py"), "--db", str(db)],
        text=True,
        capture_output=True,
        check=True,
    )
    config = json.loads(result.stdout)["mcpServers"]["compass"]
    assert config["command"] == str(Path(sys.executable).absolute())
    assert config["env"] == {"COMPASS_DB": str(db)}
    assert not db.parent.exists()


def test_explicit_python_symlink_is_not_resolved(tmp_path):
    interpreter = tmp_path / "venv python"
    interpreter.symlink_to(sys.executable)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/configure_mcp.py"),
            "--python",
            str(interpreter),
            "--db",
            str(tmp_path / "decisions.sqlite3"),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["mcpServers"]["compass"]["command"] == str(interpreter)


def test_missing_interpreter_fails_without_configuration(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/configure_mcp.py"),
            "--python",
            str(tmp_path / "absent"),
            "--db",
            str(tmp_path / "decisions.sqlite3"),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Python interpreter does not exist" in result.stderr

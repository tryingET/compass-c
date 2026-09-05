from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from install_skill import file_map, install

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "compass"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def test_generated_skill_is_current() -> None:
    process = run("scripts/build_skill.py", "--check")
    assert process.returncode == 0, process.stdout + process.stderr


def test_standalone_skill_executes_real_calculation() -> None:
    process = run(
        "-I",
        "-B",
        "skills/compass/scripts/compass.py",
        "calculate",
        "bundle",
        "--parameters",
        '{"test_accuracy":0.95,"test_cost":3,"gain":100,"loss":400}',
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout)["data"]["result"]["pair_value"] == pytest.approx(20.25)


def test_skill_validator_passes() -> None:
    process = run("scripts/validate_skill.py")
    assert process.returncode == 0, process.stdout + process.stderr


def test_install_is_self_contained_and_no_overwrite(tmp_path: Path) -> None:
    destination = install(tmp_path)
    assert destination == tmp_path / "compass"
    assert file_map(destination) == file_map(SKILL)
    with pytest.raises(FileExistsError):
        install(tmp_path)


def test_install_dry_run_has_no_side_effect(tmp_path: Path) -> None:
    root = tmp_path / "absent" / "skills"
    destination = install(root, dry_run=True)
    assert destination == root / "compass"
    assert not root.exists()


def test_replacement_requires_publication_and_permission(tmp_path: Path) -> None:
    install(tmp_path)
    with pytest.raises(ValueError, match="repository and --commit"):
        install(tmp_path, replace=True)
    with pytest.raises(ValueError, match="permission"):
        install(
            tmp_path,
            replace=True,
            repository="tryingET/compass-c",
            commit="a" * 40,
        )


def test_archives_are_deterministic_and_exclude_state(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for output in (first, second):
        process = run("scripts/build_archives.py", "--output", str(output))
        assert process.returncode == 0, process.stdout + process.stderr
    for first_path in sorted(first.glob("*.zip")):
        second_path = second / first_path.name
        assert first_path.read_bytes() == second_path.read_bytes()
        with zipfile.ZipFile(first_path) as archive:
            names = archive.namelist()
            assert any(name.endswith("/MANIFEST_SHA256.txt") for name in names)
            assert not any(
                "__pycache__" in name or name.endswith((".db", ".sqlite", ".sqlite3", ".pyc"))
                for name in names
            )

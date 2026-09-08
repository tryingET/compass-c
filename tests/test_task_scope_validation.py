from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def scope_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    scripts = checkout / "scripts"
    (scripts / "lib").mkdir(parents=True)
    for relative in ("check-task-scope-snapshots.sh", "lib/check-task-scope-snapshots.py"):
        shutil.copy2(ROOT / "scripts" / relative, scripts / relative)
    return checkout


def check_scopes(checkout: Path, entrypoint: str) -> subprocess.CompletedProcess[str]:
    missing_ak = str(checkout / "unavailable-ak")
    if entrypoint == "shell":
        command = ["sh", str(checkout / "scripts/check-task-scope-snapshots.sh")]
    else:
        command = [
            sys.executable,
            str(checkout / "scripts/lib/check-task-scope-snapshots.py"),
            "--repo-root",
            str(checkout),
            "--ak",
            missing_ak,
            "--snapshots-dir",
            "./governance/task-scopes",
        ]
    return subprocess.run(
        command,
        cwd=checkout,
        env={**os.environ, "AK_CMD": missing_ak},
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


@pytest.mark.parametrize("entrypoint", ["shell", "helper"])
@pytest.mark.parametrize("directory_state", ["absent", "empty", "unrelated"])
def test_no_snapshots_need_no_ak_authority(
    tmp_path: Path, entrypoint: str, directory_state: str
) -> None:
    checkout = scope_checkout(tmp_path)
    snapshots = checkout / "governance/task-scopes"
    if directory_state != "absent":
        snapshots.mkdir(parents=True)
    if directory_state == "unrelated":
        (snapshots / "README.md").write_text("No exported scopes.\n")
    before = sorted(path.relative_to(checkout) for path in checkout.rglob("*"))

    result = check_scopes(checkout, entrypoint)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "ok: no task-scope snapshots to validate"
    assert result.stderr == ""
    assert sorted(path.relative_to(checkout) for path in checkout.rglob("*")) == before


@pytest.mark.parametrize("entrypoint", ["shell", "helper"])
def test_existing_snapshot_fails_closed_without_ak(tmp_path: Path, entrypoint: str) -> None:
    checkout = scope_checkout(tmp_path)
    snapshots = checkout / "governance/task-scopes/nested"
    snapshots.mkdir(parents=True)
    snapshot = snapshots / "AK-123.snapshot.json"
    snapshot.write_text('{"fixture": "unvalidated snapshot"}\n')

    result = check_scopes(checkout, entrypoint)

    assert result.returncode != 0
    assert "missing" in result.stderr
    assert "unavailable-ak" in result.stderr
    assert "ok:" not in result.stdout
    assert snapshot.read_text() == '{"fixture": "unvalidated snapshot"}\n'

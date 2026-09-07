"""Executable BDD scenarios for features/installer_verification.feature."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import install_skill

REPOSITORY = "tryingET/compass-c"
COMMIT = "a" * 40


def tree_snapshot(root: Path):
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


@pytest.fixture
def verification(monkeypatch):
    boundary = Mock(
        return_value={
            "repository": REPOSITORY,
            "commit": COMMIT,
            "public_head_verified": True,
        }
    )
    monkeypatch.setattr(install_skill, "verify_published", boundary)
    return boundary


def test_publication_dry_run_verifies_source_without_filesystem_changes(tmp_path, verification):
    root = tmp_path / "absent" / "skills"
    before = tree_snapshot(tmp_path)

    destination = install_skill.install(root, dry_run=True, repository=REPOSITORY, commit=COMMIT)

    verification.assert_called_once_with(install_skill.SOURCE, REPOSITORY, COMMIT)
    assert destination == root / "compass"
    assert tree_snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("Published skill mismatch: SKILL.md"),
        RuntimeError("GitHub read failed: unavailable"),
    ],
)
def test_publication_dry_run_fails_closed_without_writes(tmp_path, verification, failure):
    root = tmp_path / "absent" / "skills"
    verification.side_effect = failure
    before = tree_snapshot(tmp_path)

    with pytest.raises(type(failure), match=str(failure)):
        install_skill.install(root, dry_run=True, repository=REPOSITORY, commit=COMMIT)

    verification.assert_called_once_with(install_skill.SOURCE, REPOSITORY, COMMIT)
    assert tree_snapshot(tmp_path) == before


def test_local_dry_run_remains_offline_without_filesystem_changes(tmp_path, verification):
    root = tmp_path / "absent" / "skills"
    before = tree_snapshot(tmp_path)

    assert install_skill.install(root, dry_run=True) == root / "compass"

    verification.assert_not_called()
    assert tree_snapshot(tmp_path) == before


@pytest.mark.parametrize("identity", [{"repository": REPOSITORY}, {"commit": COMMIT}])
def test_partial_publication_identity_is_rejected_before_verification(
    tmp_path, verification, identity
):
    before = tree_snapshot(tmp_path)

    with pytest.raises(ValueError, match="repository and commit together"):
        install_skill.install(tmp_path / "skills", dry_run=True, **identity)

    verification.assert_not_called()
    assert tree_snapshot(tmp_path) == before


def test_replacement_dry_run_requires_permission_before_verification(tmp_path, verification):
    root = tmp_path / "skills"
    existing = root / "compass"
    existing.mkdir(parents=True)
    (existing / "owned.txt").write_text("keep existing skill", encoding="utf-8")
    before = tree_snapshot(tmp_path)

    with pytest.raises(ValueError, match="permission record"):
        install_skill.install(
            root,
            dry_run=True,
            replace=True,
            repository=REPOSITORY,
            commit=COMMIT,
        )

    verification.assert_not_called()
    assert tree_snapshot(tmp_path) == before


def test_authorized_replacement_dry_run_verifies_and_preserves_existing_skill(
    tmp_path, verification
):
    root = tmp_path / "skills"
    existing = root / "compass"
    existing.mkdir(parents=True)
    (existing / "owned.txt").write_text("keep existing skill", encoding="utf-8")
    permission = tmp_path / "permission.txt"
    permission.write_text("Operator-supplied fixture permission", encoding="utf-8")
    before = tree_snapshot(tmp_path)

    result = install_skill.install(
        root,
        dry_run=True,
        replace=True,
        repository=REPOSITORY,
        commit=COMMIT,
        permission_file=permission,
    )

    verification.assert_called_once_with(install_skill.SOURCE, REPOSITORY, COMMIT)
    assert result == existing
    assert tree_snapshot(tmp_path) == before


def test_cli_publication_dry_run_reports_verification_failure(
    tmp_path, verification, monkeypatch, capsys
):
    verification.side_effect = ValueError("Published skill mismatch: SKILL.md")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_skill.py",
            "--root",
            str(tmp_path / "skills"),
            "--dry-run",
            "--repository",
            REPOSITORY,
            "--commit",
            COMMIT,
        ],
    )
    before = tree_snapshot(tmp_path)

    assert install_skill.main() == 2

    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "installed": False,
        "error": "Published skill mismatch: SKILL.md",
    }
    assert tree_snapshot(tmp_path) == before

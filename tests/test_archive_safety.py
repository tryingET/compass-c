"""Host dogfooding must not turn runtime caches into distribution artifacts."""

import pytest

from scripts import build_archives


@pytest.mark.parametrize(
    "name",
    [
        ".ontology/nexus/workspace-binding.json",
        ".ontology/snapshots/session/overlay.diff",
        ".pytest_cache/v/cache/nodeids",
        ".ruff_cache/version/cache",
        "scratch/decisions.db-wal",
        "scratch/decisions.db-shm",
        "scratch/decisions.db-journal",
        "scratch/decisions.sqlite-wal",
        "scratch/decisions.sqlite-shm",
        "scratch/decisions.sqlite3-wal",
        "scratch/decisions.sqlite3-shm",
        "scratch/decisions.sqlite3-journal",
    ],
)
def test_runtime_cache_and_sqlite_sidecars_excluded(tmp_path, monkeypatch, name):
    monkeypatch.setattr(build_archives, "ROOT", tmp_path)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic private runtime state")
    assert not build_archives.included(path)


@pytest.mark.parametrize(
    "name",
    [
        ".pi/skills/maintainer/SKILL.md",
        "src/compass_c/notebook.py",
        "docs/project/vision.md",
    ],
)
def test_source_resources_remain_included(tmp_path, monkeypatch, name):
    monkeypatch.setattr(build_archives, "ROOT", tmp_path)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic source")
    assert build_archives.included(path)

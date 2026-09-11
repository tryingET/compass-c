"""Exercise the real source builder against a synthetic dirty checkout."""

import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sdist_excludes_runtime_state_without_gitignore(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copyfile(ROOT / name, checkout / name)
    shutil.copytree(ROOT / "src", checkout / "src", ignore=shutil.ignore_patterns("__pycache__"))
    forbidden = [
        ".ontology/nexus/workspace-binding.json",
        ".ontology/snapshots/session/overlay.diff",
        ".pytest_cache/v/cache/nodeids",
        ".ruff_cache/version/cache",
        "scratch/decisions.sqlite3",
        "scratch/decisions.sqlite3-wal",
        "scratch/decisions.sqlite3-shm",
        "scratch/decisions.sqlite3-journal",
    ]
    for name in forbidden:
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic private runtime state")
    output = tmp_path / "built"
    subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(output)],
        cwd=checkout,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    (archive,) = output.glob("*.tar.gz")
    with tarfile.open(archive) as source:
        names = {name.partition("/")[2] for name in source.getnames()}
    assert not names.intersection(forbidden)
    assert {"src/compass_c/__init__.py", "README.md", "LICENSE"} <= names

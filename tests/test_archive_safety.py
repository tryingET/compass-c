"""Executable BDD scenarios for features/archive_safety.feature."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("compass_archive_builder", ROOT / "scripts/build_archives.py")
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def write(root: Path, name: str, content: str = "declared source\n") -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    root.mkdir()
    for name in (
        "README.md",
        "LICENSE",
        "pyproject.toml",
        "scripts/build_archives.py",
        "src/compass_c/core.py",
        "skills/compass/SKILL.md",
        "skills/compass/scripts/compass.py",
        ".pi/skills/compass-c-maintainer/SKILL.md",
        "tools/rocs-cli/runtime/vendor.py",
        "docs/reference.md",
    ):
        write(root, name)
    git(root, "init", "--quiet")
    git(root, "add", ".")
    return root


def build(root: Path, output: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setattr(builder, "ROOT", root)
    monkeypatch.setattr(builder, "SKILL", root / "skills/compass")
    monkeypatch.setattr(sys, "argv", ["build_archives.py", "--output", str(output)])
    assert builder.main() == 0
    return {path.name: path for path in output.glob("*.zip")}


def entries(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name.split("/", 1)[1]: archive.read(name) for name in archive.namelist()}


def test_build_excludes_untracked_files_including_nested_skill_files(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = "PRIVATE SYNTHETIC MATERIAL\n"
    for name in (
        "personal-notes.txt",
        "pytest-of-root/private-notes.txt",
        ".pytest_cache/v/cache/nodeids",
        ".ruff_cache/private",
        "src/compass_c/customer-token.txt",
        "skills/compass/references/private-notes.txt",
        ".env",
        "private.key",
    ):
        write(checkout, name, private)
    write(checkout, "README.md", "current tracked edit\n")
    products = build(checkout, tmp_path / "output", monkeypatch)
    for path in products.values():
        assert all(private.encode() not in data for data in entries(path).values())
    toolkit = entries(products[f"COMPASS-C_toolkit_v{builder.VERSION}.zip"])
    assert toolkit["README.md"] == b"current tracked edit\n"
    assert ".pi/skills/compass-c-maintainer/SKILL.md" in toolkit
    assert "tools/rocs-cli/runtime/vendor.py" in toolkit


def test_accidentally_tracked_secrets_state_caches_and_receipts_are_excluded(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsafe = (
        "private.pem",
        "private.key",
        ".pytest_cache/v/cache/nodeids",
        ".ruff_cache/private",
        ".coverage",
        "notebook.sqlite3-wal",
        "notebook.db-shm",
        "skills/compass/.install-receipt.json",
        "installation-receipt.json",
    )
    for name in unsafe:
        write(checkout, name, "SYNTHETIC PRIVATE VALUE\n")
    git(checkout, "add", "--force", ".")
    products = build(checkout, tmp_path / "output", monkeypatch)
    for path in products.values():
        assert all(b"SYNTHETIC PRIVATE VALUE" not in data for data in entries(path).values())


def test_symlinked_parent_cannot_package_external_contents(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (checkout / "docs/reference.md").unlink()
    (checkout / "docs").rmdir()
    outside = tmp_path / "outside"
    write(outside, "reference.md", "EXTERNAL PRIVATE SOURCE\n")
    (checkout / "docs").symlink_to(outside, target_is_directory=True)
    products = build(checkout, tmp_path / "output", monkeypatch)
    assert all(
        b"EXTERNAL PRIVATE SOURCE" not in data
        for path in products.values()
        for data in entries(path).values()
    )


def test_extracted_toolkit_rebuilds_without_git_and_ignores_new_local_notes(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = build(checkout, tmp_path / "original", monkeypatch)
    with zipfile.ZipFile(original[f"COMPASS-C_toolkit_v{builder.VERSION}.zip"]) as archive:
        archive.extractall(tmp_path / "extracted")
    extracted = tmp_path / "extracted/compass-c"
    assert not (extracted / ".git").exists()
    write(extracted, "personal-notes.txt", "DO NOT SHIP\n")
    rebuilt = build(extracted, tmp_path / "rebuilt", monkeypatch)
    assert original.keys() == rebuilt.keys()
    for name in original:
        assert original[name].read_bytes() == rebuilt[name].read_bytes()


def test_undeclared_tree_is_rejected_instead_of_recursively_archived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "unmanaged"
    write(root, "LICENSE")
    write(root, "skills/compass/SKILL.md")
    with pytest.raises(ValueError, match="(?i)(manifest|index|git)"):
        build(root, tmp_path / "output", monkeypatch)


def test_manifest_path_traversal_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "unmanaged"
    write(root, "LICENSE")
    write(root, "skills/compass/SKILL.md")
    write(root, "MANIFEST_SHA256.txt", "0" * 64 + "  ../private.txt\n")
    with pytest.raises(ValueError, match="(?i)(manifest|path)"):
        build(root, tmp_path / "output", monkeypatch)

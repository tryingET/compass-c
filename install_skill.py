#!/usr/bin/env python3
"""Install the local COMPASS skill with no-overwrite and verified replacement."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "skills" / "compass"
REPOSITORY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
SHA_RE = re.compile(r"[a-f0-9]{40}")


def safe_path(path: Path) -> Path:
    absolute = Path(os.path.abspath(path.expanduser()))
    for part in (absolute, *absolute.parents):
        if part.is_symlink():
            raise ValueError(f"Symlink path is not accepted: {part}")
    return absolute


def file_map(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlink in skill: {path}")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.name == ".install-receipt.json":
            continue
        if path.suffix in {".db", ".sqlite", ".sqlite3"}:
            raise ValueError("Skill distribution contains notebook state")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if "SKILL.md" not in result or "scripts/compass.py" not in result:
        raise ValueError("Incomplete skill distribution")
    return result


def github_json(endpoint: str) -> dict:
    process = subprocess.run(
        ["gh", "api", endpoint], capture_output=True, text=True, timeout=45, check=False
    )
    if process.returncode:
        raise RuntimeError(f"GitHub read failed: {process.stderr.strip()}")
    data = json.loads(process.stdout)
    if not isinstance(data, dict):
        raise ValueError("Unexpected GitHub response")
    return data


def verify_published(source: Path, repository: str, commit: str) -> dict[str, object]:
    if not REPOSITORY_RE.fullmatch(repository) or not SHA_RE.fullmatch(commit):
        raise ValueError("Use owner/repo and a full lowercase commit SHA")
    metadata = github_json(f"repos/{repository}")
    if metadata.get("private") is not False:
        raise ValueError("Expected a public repository")
    if metadata.get("full_name", "").casefold() != repository.casefold():
        raise ValueError("Repository identity mismatch")
    branch = metadata.get("default_branch")
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
        raise ValueError("Unexpected default branch")
    reference = github_json(f"repos/{repository}/git/ref/heads/{branch}")
    if reference.get("object", {}).get("sha") != commit:
        raise ValueError("Commit is not the public default-branch head")
    tree = github_json(f"repos/{repository}/git/trees/{commit}?recursive=1")
    if tree.get("truncated") is not False:
        raise ValueError("Cannot verify a truncated Git tree")
    prefix = "skills/compass/"
    remote = {
        item["path"][len(prefix) :]: item
        for item in tree.get("tree", [])
        if item.get("type") == "blob" and item.get("path", "").startswith(prefix)
    }
    local = file_map(source)
    if set(local) != set(remote):
        raise ValueError("Local skill file list differs from the published commit")
    for name in local:
        raw = (source / name).read_bytes()
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if remote[name].get("sha") != blob:
            raise ValueError(f"Published skill mismatch: {name}")
    return {"repository": repository, "commit": commit, "public_head_verified": True}


def smoke(source: Path) -> None:
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(source / "scripts" / "compass.py"),
            "calculate",
            "bundle",
            "--parameters",
            '{"test_accuracy":0.95,"test_cost":3,"gain":100,"loss":400}',
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if process.returncode:
        raise RuntimeError("Staged skill smoke check failed")
    value = json.loads(process.stdout)["data"]["result"]["pair_value"]
    if abs(value - 20.25) > 1e-9:
        raise RuntimeError("Staged skill returned an unexpected calculation")


def permission_record(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    document = safe_path(path)
    if not document.is_file() or not document.read_text(encoding="utf-8").strip():
        raise ValueError("Permission record must be a non-empty UTF-8 file")
    return {
        "document_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
        "status": "operator_supplied_not_legally_verified",
    }


def install(
    root: Path,
    *,
    dry_run: bool = False,
    replace: bool = False,
    repository: str | None = None,
    commit: str | None = None,
    permission_file: Path | None = None,
) -> Path:
    root = safe_path(root)
    destination = safe_path(root / "compass")
    expected = file_map(SOURCE)
    if destination.exists() and not replace:
        raise FileExistsError(f"Refusing to overwrite {destination}; pass --replace")
    if destination.exists() and not destination.is_dir():
        raise ValueError("Destination is not a skill directory")
    if replace and (not repository or not commit):
        raise ValueError("Replacement requires --repository and --commit")
    if bool(repository) != bool(commit):
        raise ValueError("Supply repository and commit together")
    permission = permission_record(permission_file)
    if replace and permission is None:
        raise ValueError("Managed replacement requires a rights-holder permission record")
    if dry_run:
        return destination
    publication = verify_published(SOURCE, repository, commit) if repository and commit else None
    root.parent.mkdir(parents=True, exist_ok=True)
    lock = root.parent / f".{root.name}-compass-install.lock"
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    backup: Path | None = None
    installed_new = False
    try:
        with tempfile.TemporaryDirectory(prefix=".compass-staging-", dir=root.parent) as temp:
            staged = Path(temp) / "compass"
            shutil.copytree(SOURCE, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            if file_map(staged) != expected:
                raise RuntimeError("Staging hash mismatch")
            smoke(staged)
            root.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                backup_root = root.parent / "compass-backups"
                backup_root.mkdir(exist_ok=True)
                backup = backup_root / f"compass-{uuid.uuid4().hex}"
                os.replace(destination, backup)
            os.replace(staged, destination)
            installed_new = True
            if file_map(destination) != expected:
                raise RuntimeError("Installed hash mismatch")
            receipt = {
                "installed": True,
                "account_installation": False,
                "backup": str(backup) if backup else None,
                "publication": publication,
                "permission": permission,
                "files_sha256": expected,
            }
            (destination / ".install-receipt.json").write_text(
                json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
            )
    except Exception:
        if installed_new and destination.exists():
            failed = root.parent / f"compass-failed-install-{uuid.uuid4().hex}"
            os.replace(destination, failed)
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    finally:
        lock.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / ".agents" / "skills")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--repository")
    parser.add_argument("--commit")
    parser.add_argument("--permission-file", type=Path)
    arguments = parser.parse_args()
    try:
        destination = install(
            arguments.root,
            dry_run=arguments.dry_run,
            replace=arguments.replace,
            repository=arguments.repository,
            commit=arguments.commit,
            permission_file=arguments.permission_file,
        )
        print(
            json.dumps(
                {
                    "destination": str(destination),
                    "installed": not arguments.dry_run,
                    "account_installation": False,
                    "dry_run": arguments.dry_run,
                }
            )
        )
        return 0
    except (OSError, ValueError, RuntimeError, shutil.Error, subprocess.SubprocessError) as exc:
        print(json.dumps({"installed": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

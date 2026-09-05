"""Wave 1 operational capabilities.

This module is deliberately independent of the source checkout: every operation is
callable as Python and the CLI is only an adapter.
"""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from rocs_cli import __version__
from rocs_cli.capabilities import class_policy
from rocs_cli.vendored import (
    compute_expected_hashes,
    parse_vendored_hashes_bytes,
    validate_vendor_source_layout,
    validate_vendor_target,
    verify_vendored_hashes,
    write_materialization_receipt,
)
from rocs_cli.workspace import git_head_sha


def _emit(value: dict[str, Any], destination: str = "-") -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if destination == "-":
        print(text, end="")
    else:
        path = Path(destination).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _exchange(a: Path, b: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise RuntimeError("atomic generation exchange unsupported")
    if renameat2(-100, os.fsencode(a), -100, os.fsencode(b), 2) != 0:
        error = ctypes.get_errno()
        raise RuntimeError(f"atomic generation exchange failed: {os.strerror(error)}")


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish_sibling(stage: Path, target: Path, *, fail_point: str | None = None) -> None:
    """Publish one complete generation atomically and restore it on a caught failure."""
    had_target = target.exists() or target.is_symlink()
    published = False
    exchanged = False
    try:
        if fail_point == "prepublish":
            raise RuntimeError("injected failure before atomic publication")
        if fail_point == "publish":
            raise RuntimeError("injected failure during atomic publication")
        if had_target:
            _exchange(target, stage)
            exchanged = True
        else:
            os.replace(stage, target)
        published = True
        _fsync_dir(target.parent)
        if fail_point == "after_publish":
            raise RuntimeError("injected failure after atomic publication")
    except BaseException:
        if exchanged:
            _exchange(target, stage)
            _fsync_dir(target.parent)
        elif published:
            _remove_path(target)
            _fsync_dir(target.parent)
        raise
    finally:
        _remove_path(stage)


def _vendor_from_assets(package: Path, pyproject: Path, readme: Path, uv_lock: Path, target: Path,
                        *, effective: str, source_commit: str | None, dry_run: bool = False,
                        use_lock: bool = True) -> dict[str, Any]:
    """Build one exact artifact from an explicit, complete asset set.

    Source and previously verified schema-3 bundles emit the new materialization
    receipt. Installed legacy wheels without build-time commit provenance retain
    schema 2 instead of inventing a Git identity or breaking bootstrap.
    """
    result = {"schema_version": 3 if source_commit else 2, "tool": "rocs-cli",
              "version": effective, "target": str(target), "dry_run": dry_run}
    if source_commit:
        result["source_commit"] = source_commit
    if dry_run:
        return result
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.parent / f".{target.name}.vendor.lock"
    lock_file = lock_path.open("a+b") if use_lock else None
    try:
        if lock_file is not None:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
        stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.stage-", dir=target.parent))
        try:
            shutil.copytree(
                package,
                stage / "src/rocs_cli",
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".ruff_cache",
                    ".mypy_cache",
                    ".pytest_cache",
                ),
            )
            pyproject_text = pyproject.read_text("utf-8")
            version_pattern = r'(?m)^(version\s*=\s*)["\'][^"\']+["\']\s*$'
            pyproject_text, replacements = re.subn(
                version_pattern, lambda match: f'{match.group(1)}"{effective}"', pyproject_text, count=1
            )
            if replacements != 1:
                raise RuntimeError("bootstrap pyproject must contain exactly one project version")
            (stage / "pyproject.toml").write_text(pyproject_text, "utf-8")
            shutil.copy2(readme, stage / "README.md")
            if not uv_lock.is_file():
                raise RuntimeError("self-contained artifact requires uv.lock")
            uv_text = uv_lock.read_text("utf-8")
            uv_pattern = r'(?m)(^name = "rocs-cli"\nversion = ")[^"]+("$)'
            uv_text, uv_replacements = re.subn(
                uv_pattern, lambda match: f"{match.group(1)}{effective}{match.group(2)}", uv_text, count=1
            )
            if uv_replacements != 1:
                raise RuntimeError("bootstrap uv.lock must contain exactly one rocs-cli package version")
            (stage / "uv.lock").write_text(uv_text, "utf-8")
            runtime = stage / "runtime"
            runtime.mkdir()
            for module_name in ("yaml", "rich", "markdown_it", "mdurl", "pygments"):
                spec = importlib.util.find_spec(module_name)
                if spec is None or spec.origin is None:
                    raise RuntimeError(f"runtime dependency is unavailable: {module_name}")
                origin = Path(spec.origin)
                if spec.submodule_search_locations:
                    shutil.copytree(origin.parent, runtime / module_name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(origin, runtime / origin.name)
            (stage / "rocs.py").write_text(
                "from pathlib import Path\nimport sys\nroot = Path(__file__).resolve().parent\nsys.path[:0] = [str(root / 'runtime'), str(root / 'src')]\nfrom rocs_cli.__main__ import main\nmain()\n",
                "utf-8",
            )
            if source_commit is not None:
                write_materialization_receipt(
                    stage,
                    upstream_version=effective,
                    source_commit=source_commit,
                )
            else:
                manifest = {
                    "schema_version": 2,
                    "artifact": "rocs-cli-self-contained",
                    "upstream_project": "ai-society/core/rocs-cli",
                    "upstream_version": effective,
                    "files": compute_expected_hashes(stage),
                }
                (stage / "VENDORED_HASHES.json").write_text(
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8"
                )
            ok, errors = verify_vendored_hashes(stage)
            if not ok:
                raise RuntimeError("staged vendor verification failed: " + "; ".join(errors))
            _publish_sibling(stage, target, fail_point=os.environ.get("ROCS_VENDOR_FAIL_AFTER"))
        finally:
            _remove_path(stage)
    finally:
        if lock_file is not None:
            lock_file.close()
    return result


def _source_commit(project: Path, *, required: bool = True) -> str | None:
    commit = git_head_sha(project)
    if commit is None:
        receipt_path = project / "VENDORED_HASHES.json"
        if receipt_path.is_file() and not receipt_path.is_symlink():
            try:
                receipt_before = receipt_path.read_bytes()
                verified, _errors = verify_vendored_hashes(
                    project, expected_receipt_bytes=receipt_before
                )
                receipt_after = receipt_path.read_bytes()
                receipt = parse_vendored_hashes_bytes(receipt_before)
            except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
                receipt = {}
                verified = False
                receipt_before = b""
                receipt_after = b"different"
            inherited = receipt.get("source_commit") if (
                verified
                and receipt_before == receipt_after
                and receipt.get("schema_version") == 3
                and receipt.get("artifact") == "rocs-cli-self-contained"
            ) else None
            commit = inherited if isinstance(inherited, str) else None
    if commit is None or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        if required:
            raise RuntimeError("schema-3 materialization requires the current Git SHA-1 source commit")
        return None
    return commit


def vendor(source: Path, target: Path, *, version: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Vendor a truthful source project; installed-distribution bootstrap is separate."""
    source, target = source.resolve(), target.expanduser().resolve()
    pyproject, readme, package = validate_vendor_source_layout(source)
    validate_vendor_target(repo_root=source, target=target)
    return _vendor_from_assets(package, pyproject, readme, source / "uv.lock", target,
                               effective=version or __version__, source_commit=_source_commit(source),
                               dry_run=dry_run)


def _vendor_installed(target: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parent
    assets = package / "_bootstrap_assets"
    for name in ("pyproject.toml", "README.md", "uv.lock"):
        if not (assets / name).is_file():
            raise RuntimeError(f"installed distribution is missing bootstrap asset: {name}")
    # Bootstrap already owns the stable consumer lock. Do not open a second lock.
    project = package.parents[1]
    return _vendor_from_assets(package, assets / "pyproject.toml", assets / "README.md",
                               assets / "uv.lock", target, effective=__version__,
                               source_commit=_source_commit(project, required=False), use_lock=False)


def verify(path: Path) -> tuple[dict[str, Any], int]:
    ok, errors = verify_vendored_hashes(path.resolve())
    return {"schema_version": 1, "ok": ok, "path": str(path.resolve()), "errors": errors}, 0 if ok else 1


def _distribution_root() -> Path:
    """Return the self-contained project root containing this package."""
    root = Path(__file__).resolve().parents[2]
    validate_vendor_source_layout(root)
    return root


def _preflight_managed_path(root: Path, rel: str, *, directory: bool = False) -> None:
    current = root
    parts = Path(rel).parts
    for index, part in enumerate(parts):
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise ValueError(f"managed path is a symlink: {rel}")
        if index < len(parts) - 1 and not stat.S_ISDIR(mode):
            raise ValueError(f"managed parent is not a directory: {rel}")
        if index == len(parts) - 1:
            expected = stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)
            if not expected:
                kind = "directory" if directory else "regular file"
                raise ValueError(f"managed path is not a {kind}: {rel}")


_VENDORED_LOCK_DIGEST_TOKEN = "__ROCS_VENDORED_LOCK_SHA256__"

_CI_WRAPPER = r'''#!/usr/bin/env bash
set -euo pipefail
# Sanitize lookup before invoking even basic helper commands.
export PATH="/usr/local/bin:/usr/bin:/bin"
unset PYTHONPATH
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo="${ROCS_REPO:-$(cd -- "$script_dir/../.." && pwd)}"
artifact="$repo/tools/rocs-cli"
python_bin="python3"
export ROCS_WORKSPACE_ROOT="${ROCS_WORKSPACE_ROOT:-$repo}"
export PYTHONDONTWRITEBYTECODE=1

# Verify with the standard library before importing or executing any bundled byte.
"$python_bin" -I -S -B - "$artifact" <<'PY'
import hashlib, json, os, stat, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve(strict=True)
lock = root / "VENDORED_HASHES.json"
trusted_lock_digest = "__ROCS_VENDORED_LOCK_SHA256__"
try:
    lock_bytes = lock.read_bytes()
    if hashlib.sha256(lock_bytes).hexdigest() != trusted_lock_digest:
        raise ValueError("lock digest does not match generated trust anchor")
    payload = json.loads(lock_bytes)
    expected = payload["files"]
except Exception as exc:
    raise SystemExit(f"ROCS bundled runtime lock invalid: {exc}")
actual = {}
for path in sorted(root.rglob("*")):
    if path == lock:
        continue
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or (not stat.S_ISREG(mode) and not stat.S_ISDIR(mode)):
        raise SystemExit(f"ROCS bundled runtime has invalid file type: {path.relative_to(root)}")
    if stat.S_ISREG(mode):
        actual[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit("ROCS bundled runtime verification failed closed")
PY
rocs=("$python_bin" -I -S -B "$artifact/rocs.py")
profile="${ROCS_CI_PROFILE:-local-dev}"
case "$profile" in
  local-dev) resolve=(--only path) ;;
  main-strict|branch-ci) resolve=(--resolve-refs --workspace-ref-mode strict) ;;
  *) echo "unknown ROCS_CI_PROFILE: $profile" >&2; exit 2 ;;
esac
"${rocs[@]}" cleanup --repo "$repo"
"${rocs[@]}" validate --repo "$repo" --json "${resolve[@]}"
"${rocs[@]}" build --repo "$repo" --json "${resolve[@]}"
'''


def bootstrap(target: Path, repo_class: str, *, dry_run: bool = False, converge: bool = False) -> dict[str, Any]:
    """Converge a repository transactionally, publishing one verified sibling stage."""
    final_target = target.expanduser().resolve()
    policy = class_policy(repo_class)
    if not final_target.is_dir():
        raise ValueError(f"target repository not found: {final_target}")
    ontology_root = "" if repo_class == "ontology_repo" else "ontology/"
    managed = [
        "tools/rocs-cli", f"{ontology_root}manifest.yaml", f"{ontology_root}src/system4d.yaml",
        "scripts/ci/full.sh", ".githooks/pre-push", ".githooks/README.md",
    ]
    legacy = [
        "scripts/audit-fleet.py", "scripts/bootstrap-repo.sh", "scripts/vendor-to.sh",
        "scripts/open-remediation-batch.sh", "scripts/run-fleet-audit-nightly.py",
        "scripts/run-fleet-audit-nightly.sh", "scripts/bump_version.py",
    ]
    changes = list(managed if policy["rocs_cli_vendored"] else []) + [p for p in legacy if (final_target / p).exists()]
    result = {
        "schema_version": 2, "operation": "converge" if converge else "bootstrap",
        "class": repo_class, "target": str(final_target), "dry_run": dry_run,
        "changes": changes, "rollback_paths": changes,
        "coordination_paths": [],
        "external_coordination_paths": [str(final_target.parent / f".{final_target.name}.rocs-bootstrap.lock")],
        "coordination_persistent": True,
    }
    managed_directories = {"tools", "tools/rocs-cli"}
    for rel in managed_directories:
        _preflight_managed_path(final_target, rel, directory=True)
    for rel in managed:
        if rel not in managed_directories and rel != "tools/rocs-cli":
            _preflight_managed_path(final_target, rel)
    lock_path = final_target.parent / f".{final_target.name}.rocs-bootstrap.lock"
    try:
        lock_mode = os.lstat(lock_path).st_mode
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(lock_mode) or not stat.S_ISREG(lock_mode):
            raise ValueError(f"external coordination path is not a regular file: {lock_path}")
    if dry_run:
        return result

    parent_fd = os.open(final_target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        lock_fd = os.open(lock_path.name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o644, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    lock_file = os.fdopen(lock_fd, "a+b")
    if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
        lock_file.close()
        raise ValueError(f"external coordination path is not a regular file: {lock_path}")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        stage = Path(tempfile.mkdtemp(prefix=f".{final_target.name}.bootstrap-stage-", dir=final_target.parent))
        try:
            shutil.copytree(final_target, stage, dirs_exist_ok=True, symlinks=True, copy_function=shutil.copy2)
            if policy["rocs_cli_vendored"]:
                _vendor_installed(stage / "tools/rocs-cli")
                if os.environ.get("ROCS_BOOTSTRAP_FAIL_AFTER") == "vendor":
                    raise RuntimeError("injected failure after vendor")
                manifest = stage / f"{ontology_root}manifest.yaml"
                manifest.parent.mkdir(parents=True, exist_ok=True)
                if not manifest.exists():
                    layer_path = "src" if repo_class == "ontology_repo" else "ontology/src"
                    manifest.write_text(
                        f"rocs:\n  layers:\n    - name: repo\n      path: {layer_path}\n  profiles:\n    default: repo-dev\n    repo-dev:\n      include_layers: [repo]\n",
                        "utf-8",
                    )
                system4d = stage / f"{ontology_root}src/system4d.yaml"
                system4d.parent.mkdir(parents=True, exist_ok=True)
                if not system4d.exists():
                    system4d.write_text("system4d: {}\n", "utf-8")
                ci = stage / "scripts/ci/full.sh"
                ci.parent.mkdir(parents=True, exist_ok=True)
                lock_digest = hashlib.sha256((stage / "tools/rocs-cli/VENDORED_HASHES.json").read_bytes()).hexdigest()
                ci.write_text(_CI_WRAPPER.replace(_VENDORED_LOCK_DIGEST_TOKEN, lock_digest), "utf-8")
                ci.chmod(0o755)
                hook = stage / ".githooks/pre-push"
                hook.parent.mkdir(parents=True, exist_ok=True)
                profile = "main-strict" if policy["gate_mode"] == "strict" else "local-dev"
                hook.write_text(
                    f'#!/bin/sh\nset -eu\nPATH=/usr/local/bin:/usr/bin:/bin; export PATH\nunset PYTHONPATH\nrepo="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"\n'
                    f'export ROCS_REPO="${{ROCS_REPO:-$repo}}"\n'
                    f'export ROCS_CI_PROFILE="${{ROCS_CI_PROFILE:-{profile}}}"\n'
                    f'cd "$repo"\nexec scripts/ci/full.sh\n',
                    "utf-8",
                )
                hook.chmod(0o755)
                (hook.parent / "README.md").write_text(
                    "Managed ROCS local gate. Run `git config core.hooksPath .githooks`.\n", "utf-8"
                )
            for rel in legacy:
                _remove_path(stage / rel)
            if os.environ.get("ROCS_BOOTSTRAP_FAIL_AFTER") == "managed":
                raise RuntimeError("injected failure after managed writes")
            if policy["rocs_cli_vendored"]:
                ok, errors = verify_vendored_hashes(stage / "tools/rocs-cli")
                if not ok:
                    raise RuntimeError("staged bootstrap verification failed: " + "; ".join(errors))
            _publish_sibling(stage, final_target, fail_point=os.environ.get("ROCS_BOOTSTRAP_FAIL_AFTER"))
        finally:
            _remove_path(stage)
    finally:
        lock_file.close()
    return result


def release_plan(version: str, *, project: Path | None = None) -> dict[str, Any]:
    import re

    if re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version) is None:
        raise ValueError(f"invalid release version: {version}")
    return {
        "schema_version": 1,
        "operation": "plan",
        "current_version": __version__,
        "target_version": version,
        "project": str((project or _distribution_root()).resolve()),
    }


def release_apply(version: str, *, project: Path | None = None) -> dict[str, Any]:
    import re

    root = (project or _distribution_root()).resolve()
    payload = release_plan(version, project=root)
    pyproject = root / "pyproject.toml"
    init_py = root / "src/rocs_cli/__init__.py"
    originals = {pyproject: pyproject.read_bytes(), init_py: init_py.read_bytes()}
    py_text, py_count = re.subn(
        r'(?m)^version = "[^"]+"$', f'version = "{version}"', originals[pyproject].decode(), count=1
    )
    init_text, init_count = re.subn(
        r'(?m)^__version__ = "[^"]+"$', f'__version__ = "{version}"', originals[init_py].decode(), count=1
    )
    if py_count != 1 or init_count != 1:
        raise ValueError("project version declarations are missing or inconsistent")
    try:
        for path, text in ((pyproject, py_text), (init_py, init_text)):
            temp = path.with_name(f".{path.name}.release-{os.getpid()}")
            temp.write_text(text, "utf-8")
            os.replace(temp, path)
    except BaseException:
        for path, data in originals.items():
            path.write_bytes(data)
        raise
    payload["operation"] = "apply"
    return payload


def cleanup(repo: Path, *, dry_run: bool = False) -> dict[str, Any]:
    root = repo.expanduser().resolve(strict=True)
    if root == Path(root.anchor) or not root.is_dir():
        raise ValueError("unsafe repository root")
    manifests = tuple(root / path for path in ("ontology/manifest.yaml", "ontology/manifest.yml", "manifest.yaml", "manifest.yml"))
    pyproject = root / "pyproject.toml"
    is_source = pyproject.is_file() and not pyproject.is_symlink() and 'name = "rocs-cli"' in pyproject.read_text("utf-8")
    if not any(path.is_file() and not path.is_symlink() for path in manifests) and not is_source:
        raise ValueError("repository identity is not verifiable")
    targets = [root / "ontology/dist", root / "dist"]
    removed: list[str] = []
    for target in targets:
        resolved = target.resolve(strict=False)
        resolved.relative_to(root)
        if target.is_symlink():
            raise ValueError(f"refusing symlink cleanup target: {target}")
    for target in targets:
        if target.exists():
            removed.append(str(target.relative_to(root)))
            if not dry_run:
                shutil.rmtree(target) if target.is_dir() else target.unlink()
    return {"schema_version": 1, "repo": str(root), "dry_run": dry_run, "removed": removed}


def doctor(repo: Path) -> tuple[dict[str, Any], int]:
    root = repo.expanduser().resolve()
    identity = {"name": "rocs-cli", "version": __version__, "executable": sys.executable}
    checks = {
        "repo": root.is_dir(),
        "manifest": any(
            (root / p).is_file()
            for p in ("ontology/manifest.yaml", "ontology/manifest.yml", "manifest.yaml", "manifest.yml")
        ),
    }
    ok = all(checks.values())
    return {"schema_version": 1, "ok": ok, "tool": identity, "checks": checks}, 0 if ok else 1


def generate(out: Path, count: int) -> dict[str, Any]:
    from rocs_cli.generator import generate_repo

    repo = generate_repo(out, count=count)
    return {"schema_version": 1, "repo": str(repo), "concepts": count}


def benchmark(command: str, count: int, runs: int) -> dict[str, Any]:
    from rocs_cli.generator import generate_repo

    with tempfile.TemporaryDirectory() as td:
        repo = generate_repo(Path(td) / "repo", count=count)
        samples = []
        env = {**os.environ, "ROCS_CACHE_DIR": str(Path(td) / "cache")}
        for _ in range(runs + 1):
            start = time.perf_counter()
            subprocess.run(
                [sys.executable, "-m", "rocs_cli", command, "--repo", str(repo), "--json"],
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            samples.append((time.perf_counter() - start) * 1000)
    warm = sorted(samples[1:])
    return {
        "schema_version": 1,
        "command": command,
        "concepts": count,
        "cold_ms": samples[0],
        "warm_ms": samples[1:],
        "warm_median_ms": warm[len(warm) // 2] if warm else 0,
    }

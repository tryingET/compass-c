from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from rocs_cli.managed_surface import managed_path_blocker


class FleetPreflightError(ValueError):
    pass


@dataclass(frozen=True)
class FileProbe:
    relpath: str
    path: Path
    present: bool
    valid: bool
    blocker: str | None = None
    text: str | None = None


def normalize_policy_repo_path(workspace_root: Path, policy_path: str) -> tuple[Path, str | None]:
    workspace_root = workspace_root.expanduser().resolve()
    raw = (policy_path or "").strip()
    p = Path(raw) if raw else Path()

    if p.is_absolute():
        resolved = p.expanduser().resolve()
    else:
        direct = (workspace_root / p).resolve()
        if direct.exists():
            resolved = direct
        else:
            parts = p.parts
            if parts and parts[0] == workspace_root.name:
                resolved = workspace_root.joinpath(*parts[1:]).resolve()
            else:
                resolved = direct

    if not raw or resolved == workspace_root:
        return resolved, "repo path is empty or resolves to workspace root"

    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        return resolved, "resolved path escapes workspace root"

    return resolved, None


def read_utf8_text(path: Path, *, label: str) -> str:
    try:
        return path.read_text("utf-8")
    except UnicodeDecodeError as exc:
        raise FleetPreflightError(f"{label} is not valid utf-8: {path}") from exc
    except OSError as exc:
        detail = exc.strerror or exc.__class__.__name__
        raise FleetPreflightError(f"could not read {label}: {path} ({detail})") from exc


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def probe_regular_file(
    path: Path,
    *,
    label: str,
    require_executable: bool = False,
    load_text: bool = False,
) -> FileProbe:
    present = _path_exists(path)
    if not present:
        return FileProbe(relpath=str(path), path=path, present=False, valid=False)

    try:
        st = os.lstat(path)
    except OSError as exc:
        detail = exc.strerror or exc.__class__.__name__
        return FileProbe(
            relpath=str(path),
            path=path,
            present=True,
            valid=False,
            blocker=f"could not inspect {label}: {detail}",
        )

    blocker: str | None = None
    if stat.S_ISLNK(st.st_mode):
        blocker = "path is a symlink"
    elif stat.S_ISDIR(st.st_mode):
        blocker = "path is a directory"
    elif not stat.S_ISREG(st.st_mode):
        blocker = "path is not a regular file"
    elif require_executable and not os.access(path, os.X_OK):
        blocker = "path is not executable"

    if blocker is not None:
        return FileProbe(relpath=str(path), path=path, present=True, valid=False, blocker=blocker)

    text = None
    if load_text:
        try:
            text = read_utf8_text(path, label=label)
        except FleetPreflightError as exc:
            return FileProbe(relpath=str(path), path=path, present=True, valid=False, blocker=str(exc))

    return FileProbe(relpath=str(path), path=path, present=True, valid=True, text=text)


def probe_managed_file(
    root: Path,
    relpath: str,
    *,
    label: str,
    require_executable: bool = False,
    load_text: bool = False,
) -> FileProbe:
    root = root.expanduser().resolve()
    path = root / relpath
    present = _path_exists(path)
    blocker = managed_path_blocker(root, path)
    if blocker is not None:
        return FileProbe(relpath=relpath, path=path, present=present, valid=False, blocker=blocker)
    probe = probe_regular_file(
        path,
        label=label,
        require_executable=require_executable,
        load_text=load_text,
    )
    return FileProbe(
        relpath=relpath,
        path=path,
        present=probe.present,
        valid=probe.valid,
        blocker=probe.blocker,
        text=probe.text,
    )


def probe_managed_candidates(
    root: Path,
    candidates: tuple[str, ...],
    *,
    label: str,
    require_executable: bool = False,
    load_text: bool = False,
) -> list[FileProbe]:
    probes: list[FileProbe] = []
    for relpath in candidates:
        probe = probe_managed_file(
            root,
            relpath,
            label=label,
            require_executable=require_executable,
            load_text=load_text,
        )
        if probe.present:
            probes.append(probe)
    return probes


def remove_stale_artifact(path: Path, *, root: Path | None = None) -> None:
    if root is not None:
        resolved_root = root.expanduser().resolve(strict=True)
        probe_path = path / ".delete-containment-probe" if path.is_dir() and not path.is_symlink() else path
        blocker = managed_path_blocker(resolved_root, probe_path)
        if blocker is not None:
            raise FleetPreflightError(f"refusing to clear stale artifact: {path} ({blocker})")
    try:
        if not path.exists() and not path.is_symlink():
            return
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
            return
        path.unlink()
    except OSError as exc:
        detail = exc.strerror or exc.__class__.__name__
        raise FleetPreflightError(f"could not clear stale artifact: {path} ({detail})") from exc


def validate_bootstrap_script(mode: str, bootstrap_script: Path) -> None:
    if mode != "apply":
        return
    probe = probe_regular_file(
        bootstrap_script.expanduser().resolve(),
        label="bootstrap script",
        require_executable=True,
    )
    if not probe.present:
        raise FleetPreflightError(f"bootstrap script not found: {bootstrap_script}")
    if not probe.valid:
        raise FleetPreflightError(f"bootstrap script is not runnable: {probe.path} ({probe.blocker})")

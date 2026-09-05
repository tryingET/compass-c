from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import yaml

from rocs_cli.errors import RocsCliError


KNOWN_COMPANIES: tuple[str, ...] = ("holdingco", "softwareco", "healthco")


def _hash_comment_index(line: str) -> int | None:
    in_single = False
    in_double = False
    escaped = False
    prev = ""

    for idx, ch in enumerate(line):
        if escaped:
            escaped = False
            prev = ch
            continue
        if ch == "\\" and in_double:
            escaped = True
            prev = ch
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            prev = ch
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            prev = ch
            continue
        if ch == "#" and not in_single and not in_double and (idx == 0 or prev.isspace()):
            return idx
        prev = ch

    return None


def strip_inline_hash_comment(line: str) -> str:
    idx = _hash_comment_index(line)
    if idx is None:
        return line
    return line[:idx].rstrip()


def strip_hash_comments(text: str) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        out.append(strip_inline_hash_comment(raw))
    return "\n".join(out)


def normalize_shell_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in strip_hash_comments(text).splitlines():
        line = raw.strip()
        if line:
            lines.append(line)
    return lines


def _iter_scalar_strings(value: Any):
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _iter_scalar_strings(key)
            yield from _iter_scalar_strings(nested)
        return
    if isinstance(value, list):
        for nested in value:
            yield from _iter_scalar_strings(nested)


def yaml_scalar_strings(text: str) -> list[str] | None:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if loaded is None:
        return []
    return list(_iter_scalar_strings(loaded))


def ensure_managed_output_dir(root: Path, path: Path, *, label: str) -> Path:
    root = root.expanduser().resolve()
    path = path.expanduser()
    blocker = managed_path_blocker(root, path / ".rocs-write-probe")
    if blocker is not None:
        raise RocsCliError(
            kind="config",
            message=f"{label} is not writable: {path} ({blocker})",
            details={"path": str(path), "blocker": blocker},
        )
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_managed_output_file(root: Path, path: Path, *, label: str) -> Path:
    root = root.expanduser().resolve()
    path = path.expanduser()
    blocker = managed_path_blocker(root, path)
    if blocker is not None:
        raise RocsCliError(
            kind="config",
            message=f"{label} is not writable: {path} ({blocker})",
            details={"path": str(path), "blocker": blocker},
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def managed_path_blocker(root: Path, path: Path) -> str | None:
    try:
        path.relative_to(root)
    except ValueError:
        return "path escapes target root"

    current = root
    try:
        rel = path.relative_to(root)
    except ValueError:
        return "path escapes target root"

    for part in rel.parts[:-1]:
        current = current / part
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as exc:
            detail = exc.strerror or exc.__class__.__name__
            return f"parent path is unreadable: {detail}"
        if stat.S_ISLNK(st.st_mode):
            return f"parent path is a symlink: {current.relative_to(root)}"
        if not stat.S_ISDIR(st.st_mode):
            return f"parent path is not a directory: {current.relative_to(root)}"

    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        detail = exc.strerror or exc.__class__.__name__
        return f"path is unreadable: {detail}"

    if stat.S_ISLNK(st.st_mode):
        return "path is a symlink"
    if stat.S_ISDIR(st.st_mode):
        return "path is a directory"
    if not stat.S_ISREG(st.st_mode):
        return "path is not a regular file"
    return None


def infer_company_from_parts(path: Path) -> str | None:
    for company in KNOWN_COMPANIES:
        if company in path.parts:
            return company
    return None


def workspace_company_inference_is_ambiguous(path: Path) -> bool:
    return "ai-society" in path.parts and infer_company_from_parts(path) is None

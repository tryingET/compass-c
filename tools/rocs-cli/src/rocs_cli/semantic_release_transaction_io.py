"""Bounded filesystem helpers for disposable semantic-release CAS stores."""
from __future__ import annotations

import hashlib
import os
import stat
import time
from pathlib import Path
from typing import Any, Iterable

from rocs_cli.semantic_release_protocol import jcs_bytes, strict_json_loads

SANDBOX_PREFIX = "rocs-semantic-release-sandbox-"
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 4096
DEFAULT_DEADLINE_MS = 2_000
_ALLOWED_FAULTS = {
    None, "before_journal", "after_journal", "after_head", "after_history",
    "after_receipt", "process_exit_after_head", "process_exit_after_history",
}


class SandboxTransactionError(RuntimeError):
    pass


class CasMismatchError(SandboxTransactionError):
    pass


class ReplayError(SandboxTransactionError):
    pass


class BlockedRecordError(SandboxTransactionError):
    pass


class EffectIndeterminateError(SandboxTransactionError):
    pass



def _closed_digest_list(values: Iterable[str]) -> list[str]:
    result = sorted(set(values))
    if len(result) > MAX_ENTRIES or any(not _valid_digest(value) for value in result):
        raise SandboxTransactionError("blocked digest list is invalid")
    return result


def _deadline(milliseconds: int) -> int:
    if not 1 <= milliseconds <= 300_000:
        raise SandboxTransactionError("deadline is outside bounded range")
    return time.monotonic_ns() + milliseconds * 1_000_000


def _digest(domain: str, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain.encode("ascii") + b"\0" + jcs_bytes(value)).hexdigest()


def _valid_digest(value: Any) -> bool:
    return type(value) is str and len(value) == 71 and value.startswith("sha256:") and all(
        character in "0123456789abcdef" for character in value[7:]
    )


def _hex_digest(value: str) -> str:
    if not _valid_digest(value):
        raise SandboxTransactionError("invalid digest")
    return value[7:]


def _require_keys(value: Any, keys: set[str]) -> None:
    if type(value) is not dict or set(value) != keys:
        raise SandboxTransactionError("closed object shape mismatch")


def _read_bounded(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise SandboxTransactionError(f"cannot open bounded file: {path.name}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= MAX_FILE_BYTES:
            raise SandboxTransactionError("bounded file is not regular or exceeds limit")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        stable = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        if len(raw) != before.st_size or any(getattr(before, key) != getattr(after, key) for key in stable):
            raise SandboxTransactionError("bounded file changed during read")
    finally:
        os.close(fd)
    return raw


def _read_json(path: Path) -> dict[str, Any]:
    value = strict_json_loads(_read_bounded(path))
    if type(value) is not dict:
        raise SandboxTransactionError("bounded JSON file is not an object")
    return value


def _write_exclusive(path: Path, raw: bytes) -> None:
    if len(raw) > MAX_FILE_BYTES:
        raise SandboxTransactionError("bounded write exceeds limit")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            if written <= 0:
                raise SandboxTransactionError("bounded write made no progress")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(path.parent)


def _replace(path: Path, raw: bytes) -> None:
    temp = path.parent / f".{path.name}.tmp-{os.getpid()}-{time.monotonic_ns()}"
    try:
        _write_exclusive(temp, raw)
        os.replace(temp, path)
        _fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def _fsync_dir(path: Path) -> None:
    if path.parent == Path("/proc/self/fd") and path.name.isdigit():
        fd = os.dup(int(path.name))
    else:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _remove_tree(root: Path) -> None:
    if root.exists() and root.name.startswith(SANDBOX_PREFIX):
        for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink()
        root.rmdir()

"""Crash-safe, default-off CAS primitives for disposable semantic-release sandboxes.

The store is intentionally incapable of opening an arbitrary production root: it
requires a newly created, explicitly named sandbox and a permanent marker with
``production_authorized=false``.  It proves append-only history, CAS, receipts,
and recovery mechanics without issuing or executing Decision 53 owner actions.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from rocs_cli.semantic_release_models import CheckedReleaseObject
from rocs_cli.semantic_release_protocol import jcs_bytes, strict_json_loads, validate_object
from rocs_cli.semantic_release_transaction_io import (
    DEFAULT_DEADLINE_MS, MAX_ENTRIES, SANDBOX_PREFIX, _ALLOWED_FAULTS,
    BlockedRecordError, CasMismatchError, EffectIndeterminateError, ReplayError,
    SandboxTransactionError, _closed_digest_list, _deadline, _digest, _fsync_dir,
    _hex_digest, _read_bounded, _read_json, _remove_tree, _replace, _require_keys, _valid_digest,
    _write_exclusive,
)

@dataclass(frozen=True)
class SandboxTransaction:
    transaction_id: str
    replay_key: str
    expected_revision: int
    expected_head_digest: str | None
    record: CheckedReleaseObject

    def body(self) -> dict[str, Any]:
        return {
            "schema": "rocs-semantic-release-sandbox-transaction.v0",
            "transaction_id": self.transaction_id,
            "replay_key": self.replay_key,
            "expected_revision": self.expected_revision,
            "expected_head_digest": self.expected_head_digest,
            "record_schema": self.record.schema,
            "record_digest": self.record.computed_digest,
            "record": self.record.to_value(),
            "production_authorized": False,
        }

    @property
    def digest(self) -> str:
        return _digest("rocs.semantic-release-sandbox-transaction.v0", self.body())


@dataclass(frozen=True)
class RecoveryResult:
    status: str
    transaction_digest: str | None


class SemanticReleaseSandboxStore:
    """One explicitly disposable append-only CAS store."""

    def __init__(self, root: Path, *, deadline_ms: int = DEFAULT_DEADLINE_MS) -> None:
        self.root = root.resolve(strict=True)
        self.deadline_ms = deadline_ms
        self.active_root = self.root / "active"
        self.history_root = self.root / "history"
        self.receipt_root = self.root / "receipts"
        self.staging_root = self.root / "staging"
        self.marker_path = self.root / "SANDBOX.json"
        self.head_path = self.active_root / "head.json"
        self.journal_path = self.root / "pending.json"
        self.lock_path = self.root / "lock"
        self._verify_layout()
        self._dir_fds = self._open_directory_anchors()

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        revoked_record_digests: Iterable[str] = (),
        superseded_record_digests: Iterable[str] = (),
        deadline_ms: int = DEFAULT_DEADLINE_MS,
    ) -> "SemanticReleaseSandboxStore":
        root = root.absolute()
        if not root.name.startswith(SANDBOX_PREFIX):
            raise SandboxTransactionError(f"sandbox name must start with {SANDBOX_PREFIX}")
        if root.exists():
            raise SandboxTransactionError("sandbox root must not already exist")
        root.mkdir(mode=0o700)
        try:
            for name in ("active", "history", "receipts", "staging"):
                (root / name).mkdir(mode=0o700)
            blocked = {
                "revoked": _closed_digest_list(revoked_record_digests),
                "superseded": _closed_digest_list(superseded_record_digests),
            }
            marker_body = {
                "schema": "rocs-semantic-release-sandbox.v0",
                "production_authorized": False,
                "blocked_record_digests": blocked,
            }
            marker = {**marker_body, "marker_digest": _digest("rocs.semantic-release-sandbox.v0", marker_body)}
            _write_exclusive(root / "SANDBOX.json", jcs_bytes(marker))
            _write_exclusive(root / "lock", b"")
        except BaseException:
            _remove_tree(root)
            raise
        return cls(root, deadline_ms=deadline_ms)

    def topology(self) -> dict[str, Path]:
        return {
            "active": self.active_root,
            "history": self.history_root,
            "receipts": self.receipt_root,
            "staging": self.staging_root,
        }

    def current_head(self) -> dict[str, Any] | None:
        deadline = _deadline(self.deadline_ms)
        with self._lock(deadline):
            self._verify_anchors()
            self._recover_locked(deadline)
            return self._current_head_locked()

    def _current_head_locked(self) -> dict[str, Any] | None:
        path = self._anchor("active", "head.json")
        if not path.exists():
            return None
        head = _read_json(path)
        _require_keys(head, {
            "schema", "revision", "record_schema", "record_digest", "prior_head_digest",
            "transaction_digest", "production_authorized", "head_digest",
        })
        body = {key: value for key, value in head.items() if key != "head_digest"}
        if (
            head["schema"] != "rocs-semantic-release-sandbox-head.v0"
            or head["production_authorized"] is not False
            or type(head["revision"]) is not int
            or head["revision"] < 1
            or head["head_digest"] != _digest("rocs.semantic-release-sandbox-head.v0", body)
        ):
            raise SandboxTransactionError("canonical sandbox head integrity mismatch")
        return head

    def apply(self, transaction: SandboxTransaction, *, fault: str | None = None) -> dict[str, Any]:
        if fault not in _ALLOWED_FAULTS:
            raise SandboxTransactionError("unknown fault injection point")
        deadline = _deadline(self.deadline_ms)
        with self._lock(deadline):
            self._verify_anchors()
            self._check(deadline, "before recovery")
            self._recover_locked(deadline)
            self._check(deadline, "after recovery")
            transaction = self._check_transaction(transaction)
            tx_digest = transaction.digest
            stage = self._stage_path(tx_digest)
            history = self._history_path(transaction.record.computed_digest)
            receipt = self._receipt_path(transaction.replay_key)
            if receipt.exists() or receipt.is_symlink():
                raise ReplayError("replay key already committed")
            head_before = self._current_head_locked()
            self._check_cas(transaction, head_before)
            if history.exists() or history.is_symlink():
                raise ReplayError("record digest already exists in immutable history")
            new_head = self._new_head(transaction, head_before)
            receipt_value = self._receipt(transaction, head_before, new_head)
            journal = self._journal(transaction, head_before, new_head, receipt_value)
            head_bytes = None if head_before is None else jcs_bytes(head_before)
            history_published = False
            try:
                _write_exclusive(stage, transaction.record.canonical_bytes)
                self._verify_anchors(); self._check(deadline, "after staging")
                if fault == "before_journal":
                    raise SandboxTransactionError("injected before journal")
                self._verify_anchors()
                _write_exclusive(self._anchor("root", "pending.json"), jcs_bytes(journal))
                self._verify_anchors(); self._check(deadline, "after journal")
                if fault == "after_journal":
                    raise SandboxTransactionError("injected after journal")
                self._verify_anchors()
                _replace(self._anchor("active", "head.json"), jcs_bytes(new_head))
                self._verify_anchors(); self._check(deadline, "after head")
                if fault == "process_exit_after_head":
                    os._exit(91)
                if fault == "after_head":
                    raise SandboxTransactionError("injected after head")
                self._verify_anchors()
                os.link(stage, history, follow_symlinks=False)
                history_published = True
                _fsync_dir(self._anchor("history"))
                self._verify_anchors(); self._check(deadline, "after history")
                if fault == "process_exit_after_history":
                    os._exit(92)
                if fault == "after_history":
                    raise EffectIndeterminateError("history committed; recovery required")
                self._verify_anchors()
                _write_exclusive(receipt, jcs_bytes(receipt_value))
                self._verify_anchors(); self._check(deadline, "after receipt")
                if fault == "after_receipt":
                    raise EffectIndeterminateError("receipt committed; recovery required")
                self._verify_anchors()
                self._cleanup_pending(stage)
                self._verify_anchors(); self._check(deadline, "after cleanup")
                return receipt_value
            except EffectIndeterminateError:
                raise
            except BaseException:
                if history_published:
                    raise EffectIndeterminateError("history committed; recovery required")
                self._restore_head(head_bytes)
                self._cleanup_pending(stage)
                raise

    def recover(self) -> RecoveryResult:
        deadline = _deadline(self.deadline_ms)
        with self._lock(deadline):
            self._verify_anchors()
            return self._recover_locked(deadline)

    def _recover_locked(self, deadline: int) -> RecoveryResult:
        journal_path = self._anchor("root", "pending.json")
        if not journal_path.exists() and not journal_path.is_symlink():
            return RecoveryResult("no_pending_transaction", None)
        self._check(deadline, "before journal read")
        journal = _read_json(journal_path)
        _require_keys(journal, {
            "schema", "transaction_digest", "replay_key", "record_digest", "record_schema",
            "prior_head", "new_head", "receipt", "journal_digest", "production_authorized",
        })
        body = {key: value for key, value in journal.items() if key != "journal_digest"}
        if (
            journal["schema"] != "rocs-semantic-release-sandbox-journal.v0"
            or journal["production_authorized"] is not False
            or journal["journal_digest"] != _digest("rocs.semantic-release-sandbox-journal.v0", body)
        ):
            raise SandboxTransactionError("pending journal integrity mismatch")
        tx_digest = journal["transaction_digest"]
        stage = self._stage_path(tx_digest)
        history = self._history_path(journal["record_digest"])
        receipt = self._receipt_path(journal["replay_key"])
        if not stage.is_file() or stage.is_symlink():
            raise SandboxTransactionError("pending staged record mismatch")
        stage_raw = _read_bounded(stage)
        checked_stage = validate_object(strict_json_loads(stage_raw))
        if (
            checked_stage.schema != journal["record_schema"]
            or checked_stage.computed_digest != journal["record_digest"]
            or checked_stage.canonical_bytes != stage_raw
        ):
            raise SandboxTransactionError("pending staged record mismatch")
        current = self._current_head_locked()
        prior = journal["prior_head"]
        new = journal["new_head"]
        if current == prior and not history.exists() and not receipt.exists():
            self._verify_anchors(); self._cleanup_pending(stage); self._verify_anchors()
            return RecoveryResult("aborted_uncommitted", tx_digest)
        if current != new:
            raise SandboxTransactionError("pending transaction has unknown canonical head")
        if history.exists():
            if history.is_symlink() or _read_bounded(history) != stage_raw:
                raise SandboxTransactionError("immutable history conflict")
        else:
            self._verify_anchors()
            os.link(stage, history, follow_symlinks=False)
            _fsync_dir(self._anchor("history"))
        self._verify_anchors(); self._check(deadline, "during recovery history publication")
        expected_receipt = journal["receipt"]
        if receipt.exists():
            if receipt.is_symlink() or _read_json(receipt) != expected_receipt:
                raise SandboxTransactionError("committed receipt conflict")
        else:
            self._verify_anchors(); _write_exclusive(receipt, jcs_bytes(expected_receipt))
        self._verify_anchors(); self._cleanup_pending(stage); self._verify_anchors()
        self._check(deadline, "after recovery cleanup")
        return RecoveryResult("completed_commit", tx_digest)

    def _check_transaction(self, transaction: SandboxTransaction) -> SandboxTransaction:
        if type(transaction) is not SandboxTransaction:
            raise SandboxTransactionError("transaction must use the closed sandbox type")
        if (type(transaction.transaction_id) is not str or type(transaction.replay_key) is not str
                or not transaction.transaction_id or not transaction.replay_key
                or len(transaction.transaction_id) > 256 or len(transaction.replay_key) > 256):
            raise SandboxTransactionError("transaction and replay identities are invalid")
        if type(transaction.expected_revision) is not int or transaction.expected_revision < 0:
            raise SandboxTransactionError("expected revision is invalid")
        if transaction.expected_head_digest is not None and not _valid_digest(transaction.expected_head_digest):
            raise SandboxTransactionError("expected head digest is invalid")
        try:
            checked = validate_object(strict_json_loads(transaction.record.canonical_bytes))
        except Exception as exc:
            raise SandboxTransactionError("record failed independent revalidation") from exc
        if (
            transaction.record.validation_scope != "schema_and_recursive_digest"
            or transaction.record.schema != checked.schema
            or transaction.record.definition != checked.definition
            or transaction.record.computed_digest != checked.computed_digest
            or transaction.record.canonical_bytes != checked.canonical_bytes
        ):
            raise SandboxTransactionError("record checked-object identity mismatch")
        marker = _read_json(self._anchor("root", "SANDBOX.json"))
        blocked = marker["blocked_record_digests"]
        if checked.computed_digest in blocked["revoked"]:
            raise BlockedRecordError("record is locally pinned as revoked")
        if checked.computed_digest in blocked["superseded"]:
            raise BlockedRecordError("record is locally pinned as superseded")
        return SandboxTransaction(
            transaction.transaction_id, transaction.replay_key, transaction.expected_revision,
            transaction.expected_head_digest, checked,
        )

    def _check_cas(self, transaction: SandboxTransaction, head: dict[str, Any] | None) -> None:
        actual_revision = 0 if head is None else head["revision"]
        actual_digest = None if head is None else head["head_digest"]
        if transaction.expected_revision != actual_revision or transaction.expected_head_digest != actual_digest:
            raise CasMismatchError("canonical head CAS mismatch")

    def _new_head(self, transaction: SandboxTransaction, prior: dict[str, Any] | None) -> dict[str, Any]:
        body = {
            "schema": "rocs-semantic-release-sandbox-head.v0",
            "revision": 1 if prior is None else prior["revision"] + 1,
            "record_schema": transaction.record.schema,
            "record_digest": transaction.record.computed_digest,
            "prior_head_digest": None if prior is None else prior["head_digest"],
            "transaction_digest": transaction.digest,
            "production_authorized": False,
        }
        return {**body, "head_digest": _digest("rocs.semantic-release-sandbox-head.v0", body)}

    def _receipt(
        self, transaction: SandboxTransaction, prior: dict[str, Any] | None, new: dict[str, Any]
    ) -> dict[str, Any]:
        body = {
            "schema": "rocs-semantic-release-sandbox-receipt.v0",
            "transaction_digest": transaction.digest,
            "replay_key": transaction.replay_key,
            "prior_head_digest": None if prior is None else prior["head_digest"],
            "resulting_head_digest": new["head_digest"],
            "record_digest": transaction.record.computed_digest,
            "status": "committed",
            "production_authorized": False,
        }
        return {**body, "receipt_digest": _digest("rocs.semantic-release-sandbox-receipt.v0", body)}

    def _journal(
        self,
        transaction: SandboxTransaction,
        prior: dict[str, Any] | None,
        new: dict[str, Any],
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        body = {
            "schema": "rocs-semantic-release-sandbox-journal.v0",
            "transaction_digest": transaction.digest,
            "replay_key": transaction.replay_key,
            "record_digest": transaction.record.computed_digest,
            "record_schema": transaction.record.schema,
            "prior_head": prior,
            "new_head": new,
            "receipt": receipt,
            "production_authorized": False,
        }
        return {**body, "journal_digest": _digest("rocs.semantic-release-sandbox-journal.v0", body)}

    def _restore_head(self, prior_bytes: bytes | None) -> None:
        if prior_bytes is None:
            self._anchor("active", "head.json").unlink(missing_ok=True)
            _fsync_dir(self._anchor("active"))
        else:
            _replace(self._anchor("active", "head.json"), prior_bytes)

    def _cleanup_pending(self, stage: Path) -> None:
        self._anchor("root", "pending.json").unlink(missing_ok=True)
        stage.unlink(missing_ok=True)
        _fsync_dir(self._anchor("root"))
        _fsync_dir(self._anchor("staging"))

    def _stage_path(self, tx_digest: str) -> Path:
        return self._anchor("staging", f"{_hex_digest(tx_digest)}.json")

    def _history_path(self, record_digest: str) -> Path:
        return self._anchor("history", f"{_hex_digest(record_digest)}.json")

    def _receipt_path(self, replay_key: str) -> Path:
        key = hashlib.sha256(replay_key.encode("utf-8")).hexdigest()
        return self._anchor("receipts", f"{key}.json")

    def _check(self, deadline: int, stage: str) -> None:
        if time.monotonic_ns() > deadline:
            raise SandboxTransactionError(f"transaction deadline exceeded {stage}")

    def _verify_layout(self) -> None:
        if not self.root.name.startswith(SANDBOX_PREFIX):
            raise SandboxTransactionError("not an explicitly named sandbox")
        paths = (self.root, self.active_root, self.history_root, self.receipt_root, self.staging_root)
        for path in paths:
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise SandboxTransactionError("sandbox layout contains non-directory or symlink")
        if len({path.resolve() for path in paths}) != len(paths):
            raise SandboxTransactionError("sandbox roots are not disjoint")
        marker = _read_json(self.marker_path)
        _require_keys(marker, {"schema", "production_authorized", "blocked_record_digests", "marker_digest"})
        body = {key: value for key, value in marker.items() if key != "marker_digest"}
        if (
            marker["schema"] != "rocs-semantic-release-sandbox.v0"
            or marker["production_authorized"] is not False
            or marker["marker_digest"] != _digest("rocs.semantic-release-sandbox.v0", body)
        ):
            raise SandboxTransactionError("sandbox marker integrity mismatch")
        if len(list(self.history_root.iterdir())) > MAX_ENTRIES or len(list(self.receipt_root.iterdir())) > MAX_ENTRIES:
            raise SandboxTransactionError("sandbox entry limit exceeded")

    def _open_directory_anchors(self) -> dict[str, int]:
        if not Path("/proc/self/fd").is_dir():
            raise SandboxTransactionError("descriptor-anchored paths are unavailable")
        paths = {"root": self.root, "active": self.active_root, "history": self.history_root,
                 "receipts": self.receipt_root, "staging": self.staging_root}
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        opened: dict[str, int] = {}
        try:
            for key, path in paths.items():
                opened[key] = os.open(path, flags)
        except BaseException:
            for fd in opened.values(): os.close(fd)
            raise
        return opened

    def _anchor(self, key: str, leaf: str | None = None) -> Path:
        base = Path("/proc/self/fd") / str(self._dir_fds[key])
        return base if leaf is None else base / leaf

    def _verify_anchors(self) -> None:
        paths = {"root": self.root, "active": self.active_root, "history": self.history_root,
                 "receipts": self.receipt_root, "staging": self.staging_root}
        for key, path in paths.items():
            anchored = os.fstat(self._dir_fds[key]); current = os.lstat(path)
            if (not stat.S_ISDIR(anchored.st_mode) or stat.S_ISLNK(current.st_mode)
                    or not stat.S_ISDIR(current.st_mode)
                    or (anchored.st_dev, anchored.st_ino) != (current.st_dev, current.st_ino)):
                raise SandboxTransactionError("sandbox directory identity drift")
        if (len(list(self._anchor("history").iterdir())) > MAX_ENTRIES
                or len(list(self._anchor("receipts").iterdir())) > MAX_ENTRIES):
            raise SandboxTransactionError("sandbox entry limit exceeded")

    def close(self) -> None:
        for fd in getattr(self, "_dir_fds", {}).values():
            try: os.close(fd)
            except OSError: pass
        self._dir_fds = {}

    def __del__(self) -> None:
        self.close()

    class _Lock:
        def __init__(self, path: Path, deadline: int) -> None:
            self.deadline = deadline
            self.fd = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))

        def __enter__(self) -> None:
            while True:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB); return
                except BlockingIOError:
                    if time.monotonic_ns() > self.deadline:
                        os.close(self.fd)
                        raise SandboxTransactionError("transaction deadline exceeded lock acquisition")
                    time.sleep(0.001)

        def __exit__(self, *_args: object) -> None:
            fcntl.flock(self.fd, fcntl.LOCK_UN); os.close(self.fd)

    def _lock(self, deadline: int) -> "SemanticReleaseSandboxStore._Lock":
        return self._Lock(self._anchor("root", "lock"), deadline)



"""Atomic persistence and crash recovery for semantic transactions."""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

from rocs_cli.intelligence import _canonical, _digest, _exact
from rocs_cli.transactions import (
    TransactionError,
    _admit_interpreted_source,
    _approval,
    _contained_file,
    _receipt,
    _safe_root,
    _sha,
    simulate_transaction,
    validate_transaction,
    verify_receipt,
)

def _exchange(a: Path, b: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True); fn = getattr(libc, "renameat2", None)
    if fn is None: raise TransactionError("atomic generation exchange unsupported")
    if fn(-100, os.fsencode(a), -100, os.fsencode(b), 2) != 0:
        err = ctypes.get_errno(); raise TransactionError(f"atomic generation exchange failed: {os.strerror(err)}")


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try: os.fsync(fd)
    finally: os.close(fd)


def _full_validate(stage: Path) -> None:
    try:
        from rocs_cli.validation_service import _schema_validation_result
        from rocs_cli.repo_view import load_repo_view
        from rocs_cli.validate import validate_repo_structure
        view = load_repo_view(stage, profile=None, resolve_refs=True)
        schema, _budget = _schema_validation_result(view, strict_placeholders=True, validate_deps=True)
        findings = list(validate_repo_structure(stage)) + schema
    except Exception as exc:
        raise TransactionError(f"ontology.validate.v1 failed: {exc}") from exc
    errors = [x for x in findings if getattr(x, "severity", "error") == "error"]
    if errors:
        detail = "; ".join(f"{getattr(x, 'rule_id', 'error')}: {getattr(x, 'message', x)}" for x in errors)
        raise TransactionError(f"ontology.validate.v1 failed: {detail}")


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            continue
        if path.is_file():
            fd = os.open(path, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        elif path.is_dir():
            _fsync_dir(path)
    _fsync_dir(root)


def _receipt_root(root: Path, receipt_root: Path) -> Path:
    rr = _safe_root(receipt_root, "receipt root")
    if rr == root or rr.is_relative_to(root) or root.is_relative_to(rr): raise TransactionError("receipt root must be disjoint from ontology root")
    if rr.parent != root.parent:
        raise TransactionError("receipt root must be a direct sibling of the ontology root")
    if rr.stat().st_dev != root.parent.stat().st_dev: raise TransactionError("receipt and generations must share a filesystem")
    return rr


def _expected_receipt(t: dict[str, Any], approver: str) -> dict[str, Any]:
    modes = {item["path"]: item["mode"] for item in t["write_preimages"]}
    post = [{"path": op["path"], "sha256": _sha(op["content"].encode("utf-8")), "mode": modes[op["path"]]}
            for op in t["operations"]]
    body = {"schema_version": 1, "transaction_digest": t["transaction_digest"], "approver": approver,
            "preimages": t["write_preimages"], "postimages": post, "status": "applied"}
    return {**body, "receipt_digest": _digest(body)}


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    """Publish a complete file atomically without ever truncating the final path."""
    temp = path.parent / f".{path.name}.tmp-{os.getpid()}-{id(value)}"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(_canonical(value)); f.flush(); os.fsync(f.fileno())
        os.link(temp, path, follow_symlinks=False)
        _fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)
        _fsync_dir(path.parent)


def _matches_generation(root: Path, images: list[dict[str, Any]]) -> bool:
    try:
        return all(
            _sha(_contained_file(root, item["path"]).read_bytes()) == item["sha256"]
            and ("mode" not in item or stat.S_IMODE(os.lstat(root / item["path"]).st_mode) == item["mode"])
            for item in images
        )
    except TransactionError:
        return False


def _tree_snapshot(root: Path, excluded: set[str]) -> dict[str, tuple[Any, ...]]:
    snapshot: dict[str, tuple[Any, ...]] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        mode = os.lstat(path).st_mode
        if path.is_symlink():
            snapshot[rel] = ("symlink", os.readlink(path))
        elif path.is_file():
            snapshot[rel] = ("file", mode & 0o7777, _sha(path.read_bytes()))
        elif path.is_dir():
            snapshot[rel] = ("dir", mode & 0o7777)
        else:
            snapshot[rel] = ("special", mode)
    return snapshot


def _same_outside_writes(a: Path, b: Path, paths: list[str]) -> bool:
    excluded = set(paths)
    return _tree_snapshot(a, excluded) == _tree_snapshot(b, excluded)


def _apply_journal_path(rr: Path, transaction_digest: str) -> Path:
    return rr / (".rocs-pending-" + transaction_digest[7:] + ".json")


def _validate_journal_images(value: Any, label: str, include_content: bool) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise TransactionError(f"{label} must be a non-empty list")
    result: list[dict[str, Any]] = []
    paths: list[str] = []
    keys = {"path", "sha256", "mode"} | ({"content_hex"} if include_content else set())
    for raw in value:
        item = _exact(raw, keys, label)
        path = item["path"]
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise TransactionError(f"unsafe {label} path")
        if (not isinstance(item["sha256"], str) or not item["sha256"].startswith("sha256:")
                or type(item["mode"]) is not int or not 0 <= item["mode"] <= 0o7777):
            raise TransactionError(f"invalid {label} authority")
        if include_content:
            try: data = bytes.fromhex(item["content_hex"])
            except (TypeError, ValueError) as exc: raise TransactionError("invalid journal preimage") from exc
            if data.hex() != item["content_hex"] or _sha(data) != item["sha256"]:
                raise TransactionError("journal preimage digest drift")
        paths.append(path); result.append(item)
    if paths != sorted(set(paths)):
        raise TransactionError(f"{label} paths are not canonical")
    return result


def _recover_journal(root: Path, rr: Path, journal: Path) -> None:
    if journal.is_symlink() or not journal.is_file():
        raise TransactionError("unsafe pending recovery journal")
    try: j = json.loads(journal.read_bytes())
    except (OSError, json.JSONDecodeError) as exc: raise TransactionError("malformed pending recovery journal") from exc
    j = _exact(j, {"schema_version", "kind", "transaction_digest", "root", "stage", "receipt_digest", "preimages", "postimages"}, "recovery journal")
    pre = _validate_journal_images(j["preimages"], "preimages", True)
    post = _validate_journal_images(j["postimages"], "postimages", False)
    if ([x["path"] for x in pre] != [x["path"] for x in post]
            or type(j["schema_version"]) is not int or j["schema_version"] != 1 or j["kind"] != "apply"
            or not isinstance(j["transaction_digest"], str) or journal != _apply_journal_path(rr, j["transaction_digest"])
            or not isinstance(j["receipt_digest"], str) or not j["receipt_digest"].startswith("sha256:")):
        raise TransactionError("recovery journal binding drift")
    # A journal for another root is not ours, but must be structurally readable so a
    # malformed journal can never evade root relevance classification.
    if j["root"] != str(root):
        return
    stage = Path(j["stage"])
    if (stage.parent != root.parent or not stage.name.startswith(".rocs-generation-")
            or stage.is_symlink() or not stage.is_dir()):
        raise TransactionError("unsafe recovery journal paths")
    receipt_path = rr / (j["receipt_digest"][7:] + ".json")
    paths = [item["path"] for item in pre]
    current_is_pre = _matches_generation(root, pre); current_is_post = _matches_generation(root, post)
    stage_is_pre = _matches_generation(stage, pre); stage_is_post = _matches_generation(stage, post)
    if not _same_outside_writes(root, stage, paths): raise TransactionError("recovery stage differs outside transaction writes")
    if receipt_path.exists():
        if receipt_path.is_symlink(): raise TransactionError("unsafe committed receipt")
        try: committed = json.loads(receipt_path.read_bytes())
        except (OSError, json.JSONDecodeError) as exc: raise TransactionError("malformed committed receipt") from exc
        if (not isinstance(committed, dict) or committed.get("receipt_digest") != j["receipt_digest"]
                or _digest({k: v for k, v in committed.items() if k != "receipt_digest"}) != j["receipt_digest"]
                or committed.get("transaction_digest") != j["transaction_digest"]
                or committed.get("preimages") != pre or committed.get("postimages") != post
                or receipt_path.read_bytes() != _canonical(committed) or not current_is_post or not stage_is_pre):
            raise TransactionError("committed recovery state is inconsistent")
        shutil.rmtree(stage)
    elif current_is_pre and stage_is_post:
        shutil.rmtree(stage)
    elif current_is_post and stage_is_pre:
        _exchange(root, stage); _fsync_dir(root.parent); shutil.rmtree(stage)
    else: raise TransactionError("recovery journal found unknown generation")
    journal.unlink(); _fsync_dir(rr)


def _recover_all_pending(root: Path, rr: Path) -> set[str]:
    # Receipt roots are constrained to direct siblings, making the complete journal
    # namespace finite and discoverable without a registry or filesystem-wide search.
    journals = list(root.parent.glob(".rocs-pending-*.json"))
    journals += list(root.parent.glob("*/.rocs-pending-*.json"))
    for journal in sorted(set(journals), key=lambda p: p.as_posix()):
        _recover_journal(root, journal.parent, journal)
    recovered: set[str] = set()
    rollback = root.parent / ".rocs-rollback-pending.json"
    if rollback.exists() or rollback.is_symlink():
        recovered.add(_recover_rollback_journal(root, rollback))
    return recovered


def _recover_pending(root: Path, rr: Path, t: dict[str, Any], receipt: dict[str, Any]) -> None:
    # Compatibility facade: recovery is ontology-wide, never incoming-transaction scoped.
    _recover_all_pending(root, rr)


def apply_transaction(tx: Any, plan: Any, capsule: Any, approval: Any, root: Path, receipt_root: Path, authority_artifact: Any, inject_failure: str | None = None) -> dict[str, Any]:
    t = validate_transaction(tx); approver = _approval(approval, t["transaction_digest"])
    root = _safe_root(root, "ontology root"); rr = _receipt_root(root, receipt_root)
    receipt = _expected_receipt(t, approver)
    import fcntl
    lock_fd = os.open(root.parent / ".rocs-transaction.lock", os.O_RDWR | os.O_CREAT, 0o600); fcntl.flock(lock_fd, fcntl.LOCK_EX)
    stage: Path | None = None; exchanged = False; recovery_complete = False
    journal = _apply_journal_path(rr, t["transaction_digest"])
    out = rr / (receipt["receipt_digest"][7:] + ".json")
    try:
        _recover_all_pending(root, rr)
        recovery_complete = True
        if out.exists() or out.is_symlink():
            raise TransactionError("content-addressed receipt already exists")
        simulate_transaction(t, plan, capsule, root, authority_artifact, _operation="transaction.apply")
        stage = Path(tempfile.mkdtemp(prefix=".rocs-generation-", dir=root.parent)); shutil.copytree(root, stage, dirs_exist_ok=True, symlinks=True)
        for op in t["operations"]: (stage / op["path"]).write_text(op["content"], "utf-8")
        _full_validate(stage)
        if not _matches_generation(stage, receipt["postimages"]):
            raise TransactionError("staged generation does not match authority receipt")
        _fsync_tree(stage)
        if inject_failure == "before_journal": raise TransactionError("injected failure before journal")
        j = {"schema_version": 1, "kind": "apply", "transaction_digest": t["transaction_digest"],
             "root": str(root), "stage": str(stage), "receipt_digest": receipt["receipt_digest"],
             "preimages": t["write_preimages"], "postimages": receipt["postimages"]}
        _write_exclusive(journal, j)
        if inject_failure == "before_exchange": raise TransactionError("injected failure before exchange")
        _exchange(root, stage); exchanged = True; _fsync_dir(root.parent)
        if inject_failure == "process_exit_after_exchange": os._exit(91)
        if inject_failure == "after_exchange": raise TransactionError("injected failure after exchange")
        if inject_failure == "receipt_write": raise TransactionError("injected receipt write failure")
        _write_exclusive(out, receipt)
        verify_receipt(receipt, t, root, _operation="transaction.apply")
        if inject_failure == "after_receipt": raise TransactionError("injected failure after durable receipt")
        journal.unlink(); _fsync_dir(rr); shutil.rmtree(stage); return receipt
    except BaseException:
        if not recovery_complete:
            raise
        committed = out.is_file() and not out.is_symlink() and out.read_bytes() == _canonical(receipt)
        if committed:
            # Receipt is the commit marker. Preserve journal + old generation for deterministic recovery.
            raise
        if exchanged and stage is not None:
            try: _exchange(root, stage); exchanged = False; _fsync_dir(root.parent)
            except Exception as exc: raise TransactionError(f"compensation failed; recovery journal retained: {exc}") from exc
        journal.unlink(missing_ok=True)
        if stage is not None: shutil.rmtree(stage, ignore_errors=True)
        raise
    finally: os.close(lock_fd)

def _recover_rollback_journal(root: Path, journal: Path) -> str:
    if journal.is_symlink() or not journal.is_file(): raise TransactionError("unsafe rollback journal")
    try: j = json.loads(journal.read_bytes())
    except (OSError, json.JSONDecodeError) as exc: raise TransactionError("malformed rollback journal") from exc
    j = _exact(j, {"schema_version", "kind", "transaction_digest", "receipt_digest", "root", "stage", "preimages", "postimages"}, "rollback journal")
    pre = _validate_journal_images(j["preimages"], "preimages", True)
    postimages = _validate_journal_images(j["postimages"], "postimages", False)
    stage = Path(j["stage"])
    if (type(j["schema_version"]) is not int or j["schema_version"] != 1 or j["kind"] != "rollback"
            or not isinstance(j["transaction_digest"], str) or not isinstance(j["receipt_digest"], str)
            or [x["path"] for x in pre] != [x["path"] for x in postimages]
            or j["root"] != str(root) or stage.parent != root.parent
            or not stage.name.startswith(".rocs-rollback-") or stage.is_symlink() or not stage.is_dir()):
        raise TransactionError("rollback journal binding mismatch")
    paths = [item["path"] for item in pre]
    post = _matches_generation(root, postimages)
    pre_match = _matches_generation(root, pre)
    stage_post = _matches_generation(stage, postimages)
    stage_pre = _matches_generation(stage, pre)
    if not _same_outside_writes(root, stage, paths):
        raise TransactionError("rollback stage differs outside transaction writes")
    if post:
        if not stage_pre:
            raise TransactionError("rollback recovery stage is not the prepared preimage generation")
        _exchange(root, stage)
        _fsync_dir(root.parent)
    elif pre_match:
        if not stage_post:
            raise TransactionError("rollback recovery stage is not the prior postimage generation")
    else:
        raise TransactionError("rollback recovery found unknown generation")
    shutil.rmtree(stage); journal.unlink(); _fsync_dir(root.parent)
    return j["transaction_digest"]


def _recover_rollback(root: Path, r: dict[str, Any]) -> bool:
    journal = root.parent / ".rocs-rollback-pending.json"
    if not journal.exists(): return False
    return _recover_rollback_journal(root, journal) == r["transaction_digest"]


def rollback_transaction(receipt: Any, tx: Any, root: Path, inject_failure: str | None = None) -> dict[str, Any]:
    r = _receipt(receipt, tx); root = _safe_root(root, "ontology root")
    import fcntl
    lock_fd = os.open(root.parent / ".rocs-transaction.lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    try:
        recovered = _recover_all_pending(root, root.parent)
        if r["transaction_digest"] in recovered:
            result: dict[str, Any] = {"ok": True, "receipt_digest": r["receipt_digest"], "status": "rolled_back"}
            conformance = _admit_interpreted_source(root, "transaction.rollback")
            if conformance is not None:
                result["source_contract_conformance"] = conformance
            return result
        verified = verify_receipt(r, tx, root, _operation="transaction.rollback")
        conformance = verified.get("source_contract_conformance")
        stage = Path(tempfile.mkdtemp(prefix=".rocs-rollback-", dir=root.parent)); exchanged = False
        journal = root.parent / ".rocs-rollback-pending.json"
        try:
            shutil.copytree(root, stage, dirs_exist_ok=True, symlinks=True)
            for item in r["preimages"]:
                target = stage / item["path"]
                target.write_bytes(bytes.fromhex(item["content_hex"])); target.chmod(item["mode"])
            restored_conformance = _admit_interpreted_source(stage, "transaction.rollback")
            if restored_conformance is not None:
                conformance = restored_conformance
            _fsync_tree(stage)
            j = {"schema_version": 1, "kind": "rollback", "transaction_digest": r["transaction_digest"],
                 "receipt_digest": r["receipt_digest"], "root": str(root), "stage": str(stage),
                 "preimages": r["preimages"], "postimages": r["postimages"]}
            _write_exclusive(journal, j)
            if inject_failure == "rollback_exchange": raise TransactionError("injected rollback failure")
            _exchange(root, stage); exchanged = True; _fsync_dir(root.parent)
            if inject_failure == "rollback_after_exchange": raise TransactionError("injected rollback failure after exchange")
            shutil.rmtree(stage); journal.unlink(); _fsync_dir(root.parent)
        except BaseException:
            if exchanged:
                try: _exchange(root, stage); _fsync_dir(root.parent)
                except Exception as exc: raise TransactionError(f"rollback compensation failed; journal retained: {exc}") from exc
            journal.unlink(missing_ok=True); shutil.rmtree(stage, ignore_errors=True); raise
        result = {"ok": True, "receipt_digest": r["receipt_digest"], "status": "rolled_back"}
        if conformance is not None:
            result["source_contract_conformance"] = conformance
        return result
    finally:
        os.close(lock_fd)

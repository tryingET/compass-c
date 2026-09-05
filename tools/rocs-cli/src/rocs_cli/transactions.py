"""Fail-closed, generation-atomic semantic transactions."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from rocs_cli.intelligence import TOOL_VERSION, MembraneError, _canonical, _digest, _exact, _path, validate_capsule

TRANSACTION_VERSION = 1
RECEIPT_VERSION = 1
TX_TOOL = "rocs-semantic-transaction/1"
DIGEST_KEYS = {"base_authority_digest", "capsule_digest", "plan_digest", "transaction_digest", "receipt_digest", "authority_artifact_digest"}
GATES = ["base-digests.v1", "owner-boundary.v1", "ontology.validate.v1"]


class TransactionError(MembraneError):
    pass


def _admit_interpreted_source(root: Path, operation: str) -> dict[str, Any] | None:
    """Re-admit source bytes only for opted-in layers; raw context capture never calls this."""
    try:
        from rocs_cli.repo_view import load_repo_view
        from rocs_cli.source_contract import SOURCE_CONTRACT_V1

        shallow = load_repo_view(root, profile=None, resolve_refs=True, load_docs=False)
        if not any(layer.source_contract == SOURCE_CONTRACT_V1 for layer in shallow.layers):
            return None
        view = load_repo_view(root, profile=None, resolve_refs=True)
        return view.source_conformance(operation, complete_success=True)
    except Exception as exc:
        raise TransactionError(f"{operation} source-contract admission failed: {exc}") from exc


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise TransactionError(f"{label} must be a sha256 digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise TransactionError(f"{label} must be a sha256 digest") from exc
    if value[7:] != value[7:].lower():
        raise TransactionError(f"{label} must be canonical lowercase hex")
    return value


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value) or value != sorted(set(value)):
        raise TransactionError(f"{label} must be a unique canonically sorted non-empty string list")
    return value


def _tx_path(value: Any) -> str:
    try:
        return _path(value)
    except MembraneError as exc:
        raise TransactionError(str(exc)) from exc


def _paths(value: Any, label: str) -> list[str]:
    result = _strings(value, label)
    for item in result:
        _tx_path(item)
    return result


def _safe_root(path: Path, label: str) -> Path:
    lexical = path.expanduser().absolute()
    if lexical.is_symlink():
        raise TransactionError(f"{label} must not be a symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise TransactionError(f"{label} must already exist") from exc
    if lexical != resolved:
        raise TransactionError(f"{label} must not traverse symlink aliases")
    if not resolved.is_dir():
        raise TransactionError(f"{label} must be a directory")
    return resolved


def _contained_file(root: Path, rel: str) -> Path:
    _tx_path(rel)
    target = root / rel
    current = root
    for part in PurePosixPath(rel).parts:
        current /= part
        if current.is_symlink():
            raise TransactionError(f"path traverses a symlink: {rel}")
    if not target.is_file() or not target.resolve().is_relative_to(root):
        raise TransactionError(f"not a contained regular file: {rel}")
    return target


def validate_capsule_current(capsule: Any, root: Path) -> dict[str, Any]:
    cap = validate_capsule(capsule)
    root = _safe_root(root, "ontology root")
    for item in cap["inputs"]:
        data = _contained_file(root, item["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"] or data != item["content"].encode("utf-8"):
            raise TransactionError(f"capsule input drift: {item['path']}")
    return cap


def validate_plan(plan: Any, capsule: Any) -> dict[str, Any]:
    keys = {"schema_version", "tool_version", "registry_version", "input_capsule_digests", "proposal_digest",
            "approval_digest", "allowed_capabilities", "read_paths", "write_paths", "authority_requirement",
            "verifier", "rollback", "operations", "plan_digest"}
    p = _exact(plan, keys, "plan"); cap = validate_capsule(capsule)
    if type(p["schema_version"]) is not int or p["schema_version"] != 1 or type(p["registry_version"]) is not int or p["registry_version"] != 1 or p["tool_version"] != TOOL_VERSION:
        raise TransactionError("unsupported plan identity")
    for key in ("proposal_digest", "approval_digest", "plan_digest"):
        _digest_value(p[key], key)
    capabilities = _strings(p["allowed_capabilities"], "allowed_capabilities")
    reads = _paths(p["read_paths"], "read_paths"); writes = _paths(p["write_paths"], "write_paths")
    if not set(capabilities).issubset({"ontology.read", "ontology.propose.write"}) or (reads and "ontology.read" not in capabilities) or (writes and "ontology.propose.write" not in capabilities):
        raise TransactionError("invalid plan capabilities")
    authority = _exact(p["authority_requirement"], {"kind", "approval_required"}, "authority requirement")
    if authority.get("kind") != "human" or type(authority.get("approval_required")) is not bool or authority["approval_required"] is not True:
        raise TransactionError("human authority is mandatory")
    if p["verifier"] != {"kind": "rocs-cli", "id": "ontology.validate.v1"}:
        raise TransactionError("closed verifier required")
    if p["plan_digest"] != _digest({k: p[k] for k in p if k != "plan_digest"}) or p["input_capsule_digests"] != [cap["capsule_digest"]]:
        raise TransactionError("plan or capsule digest drift")
    if p["rollback"] != {"kind": "restore", "paths": p["write_paths"]} or not isinstance(p["operations"], list) or [o.get("path") if isinstance(o, dict) else None for o in p["operations"]] != p["write_paths"]:
        raise TransactionError("plan operation/rollback closure drift")
    for op in p["operations"]:
        if _exact(op, {"op", "path", "content"}, "operation")["op"] != "replace_text" or not isinstance(op["content"], str):
            raise TransactionError("invalid operation")
    return p


def validate_authority_artifact(value: Any, capsule: Any, owner: str, ontology_root: Path) -> dict[str, Any]:
    a = _exact(value, {"schema_version", "owner", "manifest", "inputs", "authority_artifact_digest"}, "authority artifact")
    if type(a["schema_version"]) is not int or a["schema_version"] != 1 or a["owner"] != owner:
        raise TransactionError("authority identity mismatch")
    cap = validate_capsule(capsule)
    root = _safe_root(ontology_root, "ontology root")
    try:
        from rocs_cli.layers import manifest_path
        manifest = manifest_path(root)
    except Exception as exc:
        raise TransactionError(f"cannot resolve authority manifest: {exc}") from exc
    manifest_rel = manifest.relative_to(root).as_posix()
    manifest_bytes = _contained_file(root, manifest_rel).read_bytes()
    expected_manifest = {"path": manifest_rel, "sha256": _sha(manifest_bytes)}
    if _exact(a["manifest"], {"path", "sha256"}, "authority manifest") != expected_manifest:
        raise TransactionError("authority manifest digest drift")
    try:
        from rocs_cli.repo_view import load_repo_view
        view = load_repo_view(root, profile=None, resolve_refs=True, load_docs=False)
    except Exception as exc:
        raise TransactionError(f"cannot derive authority layers: {exc}") from exc
    for item in cap["inputs"]:
        target = _contained_file(root, item["path"]).resolve()
        matches = [
            layer for layer in view.layers
            if target == layer.src_root.resolve() or target.is_relative_to(layer.src_root.resolve())
        ]
        if len(matches) != 1 or matches[0].kind != item["layer"]:
            raise TransactionError(f"capsule layer claim disagrees with manifest authority: {item['path']}")
    expected = [{"path": x["path"], "layer": x["layer"], "sha256": x["sha256"]} for x in cap["inputs"]]
    if a["inputs"] != expected:
        raise TransactionError("authority inputs do not bind the capsule")
    _digest_value(a["authority_artifact_digest"], "authority_artifact_digest")
    if a["authority_artifact_digest"] != _digest({k: a[k] for k in a if k != "authority_artifact_digest"}):
        raise TransactionError("authority artifact digest drift")
    return a


def prepare_transaction(plan: Any, capsule: Any, ontology_root: Path, effects: Any, owner: str, authority_artifact: Any) -> dict[str, Any]:
    p = validate_plan(plan, capsule); cap = validate_capsule_current(capsule, ontology_root)
    _admit_interpreted_source(ontology_root, "transaction.prepare")
    if not isinstance(owner, str) or not owner.startswith("owner:") or owner == "owner:" or owner.strip() != owner:
        raise TransactionError("invalid owner")
    authority = validate_authority_artifact(authority_artifact, cap, owner, ontology_root)
    keys = {"meaning_delta", "affected_concept_ids", "affected_relation_ids", "affected_edge_ids", "bridge_blast_radius",
            "code_blast_radius", "migration_obligations", "deprecation_obligations", "owner_effects"}
    e = _exact(effects, keys, "effects")
    if not isinstance(e["meaning_delta"], str) or not e["meaning_delta"].strip(): raise TransactionError("meaning_delta must be non-empty")
    for key in keys - {"meaning_delta", "owner_effects"}: _strings(e[key], key)
    if not isinstance(e["owner_effects"], list) or not e["owner_effects"]: raise TransactionError("owner_effects required")
    partition: list[str] = []
    for item in e["owner_effects"]:
        item = _exact(item, {"owner", "paths"}, "owner effect")
        if item["owner"] != owner: raise TransactionError("cross-owner writes forbidden")
        partition += _paths(item["paths"], "owner paths")
    if partition != p["write_paths"] or len(partition) != len(set(partition)): raise TransactionError("owner partition drift")
    layers = {x["path"]: x["layer"] for x in cap["inputs"]}
    if any(layers.get(x) != "path" for x in p["write_paths"]): raise TransactionError("ref/undeclared write forbidden")
    root = _safe_root(ontology_root, "ontology root"); pre = []
    for rel in p["write_paths"]:
        target = _contained_file(root, rel)
        data = target.read_bytes()
        pre.append({"path": rel, "sha256": _sha(data), "content_hex": data.hex(),
                    "mode": stat.S_IMODE(os.lstat(target).st_mode)})
    authority_body = {"owner": owner, "manifest": authority["manifest"], "inputs": authority["inputs"], "capsule_digest": cap["capsule_digest"], "authority_artifact_digest": authority["authority_artifact_digest"]}
    body = {"schema_version": 1, "tool_version": TX_TOOL, "base_authority_digest": _digest(authority_body),
            "authority_artifact_digest": authority["authority_artifact_digest"], "capsule_digest": cap["capsule_digest"],
            "plan_digest": p["plan_digest"], "owner": owner, **e, "write_preimages": pre, "acceptance_gates": GATES,
            "rollback_contract": {"kind": "byte-exact-restore", "paths": p["write_paths"]}, "operations": p["operations"]}
    return {**body, "transaction_digest": _digest(body)}


def validate_transaction(tx: Any) -> dict[str, Any]:
    keys = {"schema_version", "tool_version", "base_authority_digest", "authority_artifact_digest", "capsule_digest", "plan_digest", "owner",
            "meaning_delta", "affected_concept_ids", "affected_relation_ids", "affected_edge_ids", "bridge_blast_radius", "code_blast_radius",
            "migration_obligations", "deprecation_obligations", "owner_effects", "write_preimages", "acceptance_gates", "rollback_contract", "operations", "transaction_digest"}
    t = _exact(tx, keys, "transaction")
    if type(t["schema_version"]) is not int or t["schema_version"] != 1 or t["tool_version"] != TX_TOOL: raise TransactionError("unsupported transaction identity")
    for key in DIGEST_KEYS & set(t): _digest_value(t[key], key)
    if not isinstance(t["owner"], str) or not t["owner"].startswith("owner:") or not isinstance(t["meaning_delta"], str) or not t["meaning_delta"].strip(): raise TransactionError("invalid transaction scalar")
    for key in ("affected_concept_ids", "affected_relation_ids", "affected_edge_ids", "bridge_blast_radius", "code_blast_radius", "migration_obligations", "deprecation_obligations"): _strings(t[key], key)
    if t["acceptance_gates"] != GATES or t["transaction_digest"] != _digest({k: t[k] for k in t if k != "transaction_digest"}): raise TransactionError("transaction digest/gate drift")
    if not isinstance(t["write_preimages"], list) or not t["write_preimages"]: raise TransactionError("preimages required")
    paths = []
    for item in t["write_preimages"]:
        item = _exact(item, {"path", "sha256", "content_hex", "mode"}, "preimage"); paths.append(_tx_path(item["path"])); _digest_value(item["sha256"], "preimage sha256")
        if not isinstance(item["content_hex"], str): raise TransactionError("content_hex must be a string")
        if type(item["mode"]) is not int or not 0 <= item["mode"] <= 0o7777:
            raise TransactionError("preimage mode must be an exact permission integer")
        try: data = bytes.fromhex(item["content_hex"])
        except ValueError as exc: raise TransactionError("malformed preimage hex") from exc
        if data.hex() != item["content_hex"] or _sha(data) != item["sha256"]: raise TransactionError("preimage digest drift")
    if paths != sorted(set(paths)) or t["rollback_contract"] != {"kind": "byte-exact-restore", "paths": paths}: raise TransactionError("rollback/preimage closure drift")
    if not isinstance(t["operations"], list) or [x.get("path") if isinstance(x, dict) else None for x in t["operations"]] != paths: raise TransactionError("operation/preimage closure drift")
    for op in t["operations"]:
        if _exact(op, {"op", "path", "content"}, "operation")["op"] != "replace_text" or not isinstance(op["content"], str): raise TransactionError("invalid operation")
    if not isinstance(t["owner_effects"], list) or not t["owner_effects"]: raise TransactionError("owner partition required")
    flat = []
    for item in t["owner_effects"]:
        item = _exact(item, {"owner", "paths"}, "owner effect")
        if item["owner"] != t["owner"]: raise TransactionError("owner partition crossing")
        flat += _paths(item["paths"], "owner paths")
    if flat != paths: raise TransactionError("owner partition drift")
    return t


def _binding(t: dict[str, Any], p: dict[str, Any], cap: dict[str, Any], authority: dict[str, Any]) -> None:
    expected = _digest({"owner": t["owner"], "manifest": authority["manifest"], "inputs": authority["inputs"], "capsule_digest": cap["capsule_digest"], "authority_artifact_digest": authority["authority_artifact_digest"]})
    if t["plan_digest"] != p["plan_digest"] or t["capsule_digest"] != cap["capsule_digest"] or t["authority_artifact_digest"] != authority["authority_artifact_digest"] or t["base_authority_digest"] != expected or t["operations"] != p["operations"]:
        raise TransactionError("trusted binding mismatch")


def _check_preimages(t: dict[str, Any], root: Path) -> None:
    root = _safe_root(root, "ontology root")
    for item in t["write_preimages"]:
        target = _contained_file(root, item["path"])
        if (_sha(target.read_bytes()) != item["sha256"]
                or stat.S_IMODE(os.lstat(target).st_mode) != item["mode"]):
            raise TransactionError(f"base bytes or mode drift: {item['path']}")


def simulate_transaction(
    tx: Any,
    plan: Any,
    capsule: Any,
    root: Path,
    authority_artifact: Any,
    *,
    _operation: str = "transaction.simulate",
) -> dict[str, Any]:
    t = validate_transaction(tx); p = validate_plan(plan, capsule); cap = validate_capsule_current(capsule, root); authority = validate_authority_artifact(authority_artifact, cap, t["owner"], root)
    conformance = _admit_interpreted_source(root, _operation)
    _binding(t, p, cap, authority); _check_preimages(t, root)
    result: dict[str, Any] = {"ok": True, "transaction_digest": t["transaction_digest"], "writes": len(t["operations"]), "mutated": False}
    if conformance is not None:
        result["source_contract_conformance"] = conformance
    return result


def _approval(value: Any, digest: str) -> str:
    a = _exact(value, {"schema_version", "transaction_digest", "approved", "approver"}, "transaction approval")
    who = a["approver"]
    if type(a["schema_version"]) is not int or a["schema_version"] != 1 or a["approved"] is not True or a["transaction_digest"] != digest or not isinstance(who, str) or not who.startswith("operator:") or who == "operator:" or who.strip() != who: raise TransactionError("invalid transaction approval")
    return who


def _receipt(value: Any, tx: Any) -> dict[str, Any]:
    t = validate_transaction(tx); r = _exact(value, {"schema_version", "transaction_digest", "approver", "preimages", "postimages", "status", "receipt_digest"}, "receipt")
    if type(r["schema_version"]) is not int or r["schema_version"] != 1 or r["status"] != "applied" or r["transaction_digest"] != t["transaction_digest"] or not isinstance(r["approver"], str) or not r["approver"].startswith("operator:") or r["approver"] == "operator:" or r["approver"].strip() != r["approver"]: raise TransactionError("receipt identity/status mismatch")
    _digest_value(r["receipt_digest"], "receipt_digest")
    if r["receipt_digest"] != _digest({k: r[k] for k in r if k != "receipt_digest"}) or r["preimages"] != t["write_preimages"]: raise TransactionError("receipt digest/preimage binding drift")
    if not isinstance(r["postimages"], list): raise TransactionError("postimages must be a list")
    posts = []
    for item in r["postimages"]:
        item = _exact(item, {"path", "sha256", "mode"}, "postimage"); posts.append(_tx_path(item["path"])); _digest_value(item["sha256"], "postimage sha256")
        if type(item["mode"]) is not int or not 0 <= item["mode"] <= 0o7777:
            raise TransactionError("postimage mode must be an exact permission integer")
    paths = [x["path"] for x in t["write_preimages"]]
    if posts != paths or posts != sorted(set(posts)): raise TransactionError("receipt path-set mismatch")
    expected = [(_sha(op["content"].encode()), t["write_preimages"][index]["mode"])
                for index, op in enumerate(t["operations"])]
    if [(x["sha256"], x["mode"]) for x in r["postimages"]] != expected:
        raise TransactionError("receipt postimages do not bind transaction bytes and modes")
    return r


def verify_receipt(
    receipt: Any,
    tx: Any,
    root: Path,
    *,
    _operation: str = "transaction.verify",
) -> dict[str, Any]:
    r = _receipt(receipt, tx); root = _safe_root(root, "ontology root")
    conformance = _admit_interpreted_source(root, _operation)
    for item in r["postimages"]:
        target = _contained_file(root, item["path"])
        if (_sha(target.read_bytes()) != item["sha256"]
                or stat.S_IMODE(os.lstat(target).st_mode) != item["mode"]):
            raise TransactionError(f"post-apply drift: {item['path']}")
    result: dict[str, Any] = {"ok": True, "receipt_digest": r["receipt_digest"], "status": r["status"]}
    if conformance is not None:
        result["source_contract_conformance"] = conformance
    return result


# Persistence and generation-atomic lifecycle implementation lives separately.
# Lazy compatibility facades also allow the store module to import validation
# primitives from this module without an import cycle.
def _store() -> Any:
    from rocs_cli import transaction_store
    return transaction_store


def _exchange(a: Path, b: Path) -> None:
    return _store()._exchange(a, b)


def _fsync_dir(path: Path) -> None:
    return _store()._fsync_dir(path)


def _full_validate(stage: Path) -> None:
    return _store()._full_validate(stage)


def _fsync_tree(root: Path) -> None:
    return _store()._fsync_tree(root)


def _receipt_root(root: Path, receipt_root: Path) -> Path:
    return _store()._receipt_root(root, receipt_root)


def _expected_receipt(t: dict[str, Any], approver: str) -> dict[str, Any]:
    return _store()._expected_receipt(t, approver)


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    return _store()._write_exclusive(path, value)


def _matches_generation(root: Path, images: list[dict[str, Any]]) -> bool:
    return _store()._matches_generation(root, images)


def _tree_snapshot(root: Path, excluded: set[str]) -> dict[str, tuple[Any, ...]]:
    return _store()._tree_snapshot(root, excluded)


def _same_outside_writes(a: Path, b: Path, paths: list[str]) -> bool:
    return _store()._same_outside_writes(a, b, paths)


def _apply_journal_path(rr: Path, transaction_digest: str) -> Path:
    return _store()._apply_journal_path(rr, transaction_digest)


def _recover_pending(root: Path, rr: Path, t: dict[str, Any], receipt: dict[str, Any]) -> None:
    return _store()._recover_pending(root, rr, t, receipt)


def apply_transaction(tx: Any, plan: Any, capsule: Any, approval: Any, root: Path,
                      receipt_root: Path, authority_artifact: Any,
                      inject_failure: str | None = None) -> dict[str, Any]:
    return _store().apply_transaction(
        tx, plan, capsule, approval, root, receipt_root, authority_artifact, inject_failure
    )


def _recover_rollback(root: Path, receipt: dict[str, Any]) -> bool:
    return _store()._recover_rollback(root, receipt)


def rollback_transaction(receipt: Any, tx: Any, root: Path,
                         inject_failure: str | None = None) -> dict[str, Any]:
    return _store().rollback_transaction(receipt, tx, root, inject_failure)

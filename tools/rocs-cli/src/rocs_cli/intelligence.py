"""Offline intelligence membrane: untrusted proposals in, deterministic plans out."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

CAPSULE_VERSION = 1
PROPOSAL_VERSION = 1
PLAN_VERSION = 1
REGISTRY_VERSION = 1
TOOL_VERSION = "rocs-intelligence-membrane/1"
CAPABILITIES = frozenset({"ontology.read", "ontology.propose.write"})


class ProposalAdapter(Protocol):
    """Optional adapter boundary. Implementations receive bytes and return proposal bytes only."""
    def propose(self, capsule: bytes) -> bytes: ...


class MembraneError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _exact(obj: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(obj, dict) or set(obj) != keys:
        actual = set(obj) if isinstance(obj, dict) else set()
        raise MembraneError(f"{label} fields must be exactly {sorted(keys)}; got {sorted(actual)}")
    return obj


def _path(raw: Any) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise MembraneError("paths must be non-empty repository-relative POSIX paths")
    p = PurePosixPath(raw)
    if p.is_absolute() or raw != p.as_posix() or any(part in ("", ".", "..") for part in p.parts):
        raise MembraneError(f"unsafe path: {raw!r}")
    return raw


def load_json(path: Path) -> Any:
    try:
        from rocs_cli.constitution import ConstitutionError, strict_json_load
        with path.open("r", encoding="utf-8") as handle:
            return strict_json_load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError, ConstitutionError) as exc:
        raise MembraneError(f"cannot read strict JSON {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(_canonical(value))


def write_compiled_plan(
    artifact_root: Path, out: str, value: Any, *, ontology_root: Path, capsule: dict[str, Any], input_files: list[Path]
) -> Path:
    """Write only to a declared, disjoint, non-symlink artifact tree."""
    if not isinstance(out, str):
        raise MembraneError("compiled output must be an artifact-root-relative path")
    rel = _path(out)
    artifact_lex = artifact_root.expanduser().absolute()
    ontology_lex = ontology_root.expanduser().absolute()
    if artifact_lex.is_symlink() or ontology_lex.is_symlink():
        raise MembraneError("artifact and ontology roots must not be symlinks")
    try:
        artifact = artifact_lex.resolve(strict=True)
        ontology = ontology_lex.resolve(strict=True)
    except OSError as exc:
        raise MembraneError(f"artifact and ontology roots must already exist: {exc}") from exc
    if not artifact.is_dir() or not ontology.is_dir():
        raise MembraneError("artifact and ontology roots must be directories")
    if artifact == ontology or artifact.is_relative_to(ontology) or ontology.is_relative_to(artifact):
        raise MembraneError("artifact root must be disjoint from the ontology root")
    destination = artifact / rel
    current = artifact
    for part in PurePosixPath(rel).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise MembraneError("compiled output must not traverse symlinks")
    if destination.exists() or destination.is_symlink():
        raise MembraneError("compiled output destination must not already exist")
    if destination.resolve(strict=False).parent != destination.parent.resolve(strict=False):
        raise MembraneError("compiled output escapes the declared artifact root")
    if not destination.resolve(strict=False).is_relative_to(artifact):
        raise MembraneError("compiled output escapes the declared artifact root")
    capsule_paths = {item["path"] for item in validate_capsule(capsule)["inputs"]}
    if rel in capsule_paths:
        raise MembraneError("compiled output collides with a path/ref-layer input")
    resolved_inputs = {path.expanduser().resolve(strict=False) for path in input_files}
    if destination.resolve(strict=False) in resolved_inputs:
        raise MembraneError("compiled output collides with an existing command input")
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(destination, flags, 0o600)
    except OSError as exc:
        raise MembraneError(f"cannot exclusively create compiled artifact: {exc}") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def create_capsule(root: Path, inputs: list[tuple[str, str]]) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not inputs:
        raise MembraneError("at least one input is required")
    records = []
    seen: set[str] = set()
    for raw, layer in sorted(inputs):
        rel = _path(raw)
        if rel in seen or layer not in {"path", "ref"}:
            raise MembraneError("capsule paths must be unique and layers must be path or ref")
        seen.add(rel)
        source = root / rel
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
            raise MembraneError(f"input is not a contained regular non-symlink file: {rel}")
        data = source.read_bytes()
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MembraneError(f"input is not UTF-8 text: {rel}") from exc
        records.append({"path": rel, "layer": layer, "sha256": hashlib.sha256(data).hexdigest(), "content": content})
    body = {"schema_version": CAPSULE_VERSION, "tool_version": TOOL_VERSION, "inputs": records}
    return {**body, "capsule_digest": _digest(body)}


def validate_capsule(value: Any) -> dict[str, Any]:
    cap = _exact(value, {"schema_version", "tool_version", "inputs", "capsule_digest"}, "capsule")
    if type(cap["schema_version"]) is not int or cap["schema_version"] != CAPSULE_VERSION or cap["tool_version"] != TOOL_VERSION or not isinstance(cap["inputs"], list) or not cap["inputs"]:
        raise MembraneError("unsupported capsule identity")
    paths = set()
    ordered_paths: list[str] = []
    for item in cap["inputs"]:
        item = _exact(item, {"path", "layer", "sha256", "content"}, "capsule input")
        rel = _path(item["path"])
        if rel in paths or item["layer"] not in {"path", "ref"} or not isinstance(item["content"], str):
            raise MembraneError("invalid capsule input")
        paths.add(rel)
        ordered_paths.append(rel)
        if not isinstance(item["sha256"], str) or item["sha256"] != hashlib.sha256(item["content"].encode()).hexdigest():
            raise MembraneError("capsule content digest drift")
    if ordered_paths != sorted(ordered_paths):
        raise MembraneError("capsule inputs are not in canonical path order")
    body = {k: cap[k] for k in ("schema_version", "tool_version", "inputs")}
    if cap["capsule_digest"] != _digest(body):
        raise MembraneError("capsule digest drift")
    return cap


def validate_proposal(value: Any, capsule: dict[str, Any]) -> tuple[dict[str, Any], str]:
    keys = {"schema_version", "capsule_digest", "registry_version", "capabilities", "read_paths", "write_paths", "authority_requirement", "verifier", "rollback", "operations"}
    p = _exact(value, keys, "proposal")
    if (type(p["schema_version"]) is not int or type(p["registry_version"]) is not int
            or p["schema_version"] != PROPOSAL_VERSION or p["registry_version"] != REGISTRY_VERSION):
        raise MembraneError("unsupported proposal or registry version")
    if p["capsule_digest"] != capsule["capsule_digest"]:
        raise MembraneError("proposal capsule digest drift")
    capabilities = p["capabilities"]
    if (not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities)
            or len(set(capabilities)) != len(capabilities) or capabilities != sorted(capabilities)
            or not set(capabilities).issubset(CAPABILITIES)):
        raise MembraneError("capabilities must be known, unique, and canonically sorted")
    declared = {i["path"]: i["layer"] for i in capsule["inputs"]}
    for field in ("read_paths", "write_paths"):
        if (not isinstance(p[field], list) or not all(isinstance(x, str) for x in p[field])
                or len(set(p[field])) != len(p[field]) or p[field] != sorted(p[field])):
            raise MembraneError(f"{field} must be a unique, canonically sorted list")
        for value_path in p[field]:
            _path(value_path)
        if not set(p[field]).issubset(declared):
            raise MembraneError(f"{field} expands undeclared capsule paths")
    if p["read_paths"] and "ontology.read" not in capabilities:
        raise MembraneError("declared reads require ontology.read")
    if p["write_paths"] and "ontology.propose.write" not in capabilities:
        raise MembraneError("declared writes require ontology.propose.write")
    if any(declared[x] == "ref" for x in p["write_paths"]):
        raise MembraneError("ref-layer writes are forbidden")
    _exact(p["authority_requirement"], {"kind", "approval_required"}, "authority requirement")
    if (p["authority_requirement"].get("kind") != "human"
            or type(p["authority_requirement"].get("approval_required")) is not bool
            or p["authority_requirement"]["approval_required"] is not True):
        raise MembraneError("human approval is required")
    _exact(p["verifier"], {"kind", "id"}, "verifier")
    if p["verifier"] != {"kind": "rocs-cli", "id": "ontology.validate.v1"}:
        raise MembraneError("invalid deterministic verifier")
    _exact(p["rollback"], {"kind", "paths"}, "rollback")
    if p["rollback"]["kind"] != "restore" or p["rollback"]["paths"] != p["write_paths"]:
        raise MembraneError("rollback must restore exact write paths")
    if not isinstance(p["operations"], list):
        raise MembraneError("operations must be a list")
    operation_paths: list[str] = []
    for op in p["operations"]:
        _exact(op, {"op", "path", "content"}, "operation")
        if ("ontology.propose.write" not in capabilities or op["op"] != "replace_text"
                or _path(op["path"]) not in p["write_paths"] or not isinstance(op["content"], str)):
            raise MembraneError("operation exceeds declared write authority")
        operation_paths.append(op["path"])
    if operation_paths != p["write_paths"]:
        raise MembraneError("operations must contain exactly one canonically ordered operation per write path")
    return p, _digest(p)


def compile_plan(proposal: dict[str, Any], proposal_digest: str, capsule: dict[str, Any], approval: Any) -> dict[str, Any]:
    capsule = validate_capsule(capsule)
    proposal, actual_digest = validate_proposal(proposal, capsule)
    if proposal_digest != actual_digest:
        raise MembraneError("proposal digest drift")
    a = _exact(approval, {"schema_version", "proposal_digest", "approved", "approver"}, "approval")
    approver = a.get("approver")
    valid_approver = (isinstance(approver, str) and approver.startswith("operator:")
                      and len(approver) > len("operator:")
                      and approver == approver.strip())
    if (type(a["schema_version"]) is not int or a["schema_version"] != 1 or a["approved"] is not True or a["proposal_digest"] != proposal_digest
            or not valid_approver):
        raise MembraneError("missing, denied, mismatched, or non-human external approval")
    body = {
        "schema_version": PLAN_VERSION, "tool_version": TOOL_VERSION, "registry_version": REGISTRY_VERSION,
        "input_capsule_digests": [capsule["capsule_digest"]], "proposal_digest": proposal_digest,
        "approval_digest": _digest(a), "allowed_capabilities": proposal["capabilities"],
        "read_paths": proposal["read_paths"], "write_paths": proposal["write_paths"],
        "authority_requirement": proposal["authority_requirement"], "verifier": proposal["verifier"],
        "rollback": proposal["rollback"], "operations": proposal["operations"],
    }
    return {**body, "plan_digest": _digest(body)}

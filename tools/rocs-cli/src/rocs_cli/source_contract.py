"""Shared opt-in admission for the ``ontology-markdown-v1`` source contract.

The semantic owner defines the grammar.  This module only evaluates exact
source-contract, schema, and reference conformance; it does not issue semantic,
publication, adoption, activation, or currentness facts.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

import yaml
from yaml.events import (
    AliasEvent,
    DocumentEndEvent,
    DocumentStartEvent,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
)
from yaml.nodes import MappingNode

SOURCE_CONTRACT_V1 = "ontology-markdown-v1"
MAX_DOCUMENT_BYTES = 1_048_576
MAX_COLLECTION_DEPTH = 32
MAX_COLLECTION_ITEMS = 10_000
_ID_RE = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_PLACEHOLDER_RE = re.compile(r"<[^>]+>")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MARKER_RE = re.compile(r"(?m)^(?:---|\.\.\.)[ \t]*(?:#.*)?$")
_PHASE_ORDER = {"resource": 1, "envelope": 2, "yaml": 3, "schema": 4, "identity": 5, "reference": 6, "placeholder": 7}
INTERPRETING_OPERATIONS = frozenset({
    "validate", "build", "summary", "lint", "diff", "graph", "check-inverses",
    "normalize", "pack", "pack.bound", "discover", "route", "transaction.prepare",
    "transaction.simulate", "transaction.apply", "transaction.verify", "transaction.rollback",
})


class SourceContractError(ValueError):
    """A fail-closed admission error with the accepted precedence class."""

    def __init__(self, phase: str, message: str, *, path: str | None = None, kind: str = "invalid_ontology"):
        super().__init__(message)
        self.phase = phase
        self.message = message
        self.path = path
        self.kind = kind
        self.precedence = _PHASE_ORDER[phase]


class SourceContractSelectorError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSourceDocument:
    raw: bytes
    text: str
    frontmatter: dict[str, Any]
    body: str
    logical_path: str
    kind: str
    collection_items: int
    source_contract: str = SOURCE_CONTRACT_V1

    @property
    def ont(self) -> dict[str, Any]:
        return self.frontmatter["ont"]

    @property
    def ont_id(self) -> str:
        return self.ont["id"]

    @property
    def ont_type(self) -> str:
        return self.ont["type"]


class _StrictLoader(yaml.SafeLoader):
    pass


# PyYAML's YAML-1.1 resolver treats yes/no/on/off as booleans.  V1 accepts only
# the exact lowercase YAML boolean spellings used by its field grammar.
_StrictLoader.yaml_implicit_resolvers = deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for _first, _resolvers in list(_StrictLoader.yaml_implicit_resolvers.items()):
    _StrictLoader.yaml_implicit_resolvers[_first] = [
        item for item in _resolvers if item[0] != "tag:yaml.org,2002:bool"
    ]
_StrictLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf")
)


def _construct_mapping(loader: _StrictLoader, node: MappingNode, deep: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge" or getattr(key_node, "value", None) == "<<":
            raise SourceContractError("yaml", "YAML merge keys are forbidden")
        key = loader.construct_object(key_node, deep=deep)
        if type(key) is not str:
            raise SourceContractError("yaml", "all YAML mapping keys must be strings")
        if key in result:
            raise SourceContractError("yaml", f"duplicate YAML mapping key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictLoader.add_constructor("tag:yaml.org,2002:map", _construct_mapping)


def _error(phase: str, message: str, path: str) -> SourceContractError:
    kind = "resource_exhausted" if phase == "resource" else "invalid_ontology"
    return SourceContractError(phase, message, path=path, kind=kind)


def _yaml_value(front: str, *, path: str, max_depth: int, max_items: int) -> tuple[Any, int]:
    if _MARKER_RE.search(front):
        raise _error("yaml", "additional YAML document markers are forbidden", path)
    stack: list[list[Any]] = []
    items = 0
    documents = 0
    try:
        for event in yaml.parse(front, Loader=_StrictLoader):
            if isinstance(event, AliasEvent):
                raise _error("yaml", "YAML aliases are forbidden", path)
            if isinstance(event, DocumentStartEvent):
                documents += 1
                if event.explicit or documents != 1:
                    raise _error("yaml", "multiple or explicit YAML documents are forbidden", path)
            if isinstance(event, DocumentEndEvent) and event.explicit:
                raise _error("yaml", "explicit YAML document endings are forbidden", path)
            is_node = isinstance(event, (ScalarEvent, MappingStartEvent, SequenceStartEvent))
            if is_node:
                if getattr(event, "anchor", None) is not None:
                    raise _error("yaml", "YAML anchors are forbidden", path)
                if getattr(event, "tag", None) is not None:
                    raise _error("yaml", "explicit YAML tags are forbidden", path)
                if stack:
                    parent = stack[-1]
                    if parent[0] == "sequence" or parent[1] % 2 == 0:
                        items += 1
                        if items > max_items:
                            raise _error("resource", "YAML collection item limit exceeded", path)
                    parent[1] += 1
            if isinstance(event, MappingStartEvent):
                stack.append(["mapping", 0])
            elif isinstance(event, SequenceStartEvent):
                stack.append(["sequence", 0])
            elif isinstance(event, (MappingEndEvent, SequenceEndEvent)):
                stack.pop()
            if len(stack) > max_depth:
                raise _error("resource", "YAML collection depth limit exceeded", path)
    except SourceContractError:
        raise
    except (yaml.YAMLError, RecursionError) as exc:
        raise _error("yaml", "frontmatter is not one valid YAML document", path) from exc
    if documents != 1:
        raise _error("yaml", "frontmatter must contain one YAML document", path)
    try:
        return yaml.load(front, Loader=_StrictLoader), items
    except SourceContractError as exc:
        if exc.path is None:
            exc.path = path
        raise
    except (yaml.YAMLError, RecursionError) as exc:
        raise _error("yaml", "frontmatter is not valid YAML", path) from exc


def _nonempty(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _string_list(value: Any, field: str, path: str, *, required: bool = False, nonempty_items: bool = False) -> None:
    valid = type(value) is list and (not required or bool(value))
    valid = valid and all(type(item) is str and (not nonempty_items or bool(item.strip())) for item in value)
    if not valid:
        qualifier = "non-empty " if required else ""
        raise _error("schema", f"ont.{field} must be a {qualifier}list of strings", path)


def _allowed_value_tree(value: Any) -> bool:
    if type(value) in (str, bool):
        return True
    if type(value) is list:
        return all(_allowed_value_tree(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _allowed_value_tree(item) for key, item in value.items())
    return False


def _exact_keys(value: Any, keys: set[str], label: str, path: str, *, phase: str = "schema") -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise _error(phase, f"{label} fields must be exactly {sorted(keys)}", path)
    return value


def _decision_ref_ok(value: str) -> bool:
    if value.startswith("https://"):
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.netloc) and not any(ord(ch) < 32 for ch in value)
    return _safe_logical_path(value)


def _safe_logical_path(value: str) -> bool:
    if not value or "\\" in value or unicodedata.normalize("NFC", value) != value or any(ord(ch) < 32 for ch in value):
        return False
    pure = PurePosixPath(value)
    return not pure.is_absolute() and pure.as_posix() == value and "//" not in value and all(part not in ("", ".", "..") for part in pure.parts)


def _validate_schema(front: Any, *, path: str) -> tuple[dict[str, Any], str]:
    if type(front) is not dict or type(front.get("ont")) is not dict:
        raise _error("schema", "frontmatter must be a mapping containing ont", path)
    ont = front["ont"]
    ont_type = ont.get("type")
    if ont_type not in ("concept", "relation") or type(ont_type) is not str:
        raise _error("schema", "ont.type must be exactly concept or relation", path)
    top_keys = {"ont", "system4d"} if ont_type == "concept" else {"ont"}
    if set(front) - top_keys or "ont" not in front:
        raise _error("schema", f"invalid top-level fields for {ont_type}", path)
    concept_keys = {"id", "type", "labels", "description", "status", "deprecated", "lint_ignore", "examples", "anti_examples", "synonyms", "relations"}
    relation_keys = {"id", "type", "labels", "description", "status", "deprecated", "lint_ignore", "examples", "anti_examples", "group", "characteristics", "axis_default", "inverse"}
    allowed = concept_keys if ont_type == "concept" else relation_keys
    required = {"id", "type", "labels", "description", "relations"} if ont_type == "concept" else {"id", "type", "labels", "description", "group", "characteristics", "axis_default"}
    if set(ont) - allowed or not required.issubset(ont):
        raise _error("schema", f"invalid ont fields for {ont_type}", path)
    if not _allowed_value_tree(front):
        raise _error("schema", "frontmatter contains a value outside the v1 YAML value profile", path)
    if not _nonempty(ont.get("id")) or not _nonempty(ont.get("description")):
        raise _error("schema", "ont.id and ont.description must be non-empty strings", path)
    _string_list(ont.get("labels"), "labels", path, required=True, nonempty_items=True)
    for field in ("examples", "anti_examples"):
        if field in ont:
            _string_list(ont[field], field, path)
    if "lint_ignore" in ont and ont["lint_ignore"] != []:
        raise _error("schema", "ont.lint_ignore must be exactly []", path)
    status = ont.get("status", "active")
    if type(status) is not str or status not in ("active", "deprecated"):
        raise _error("schema", "ont.status must be exactly active or deprecated", path)
    if status == "active" and "deprecated" in ont:
        raise _error("schema", "ont.deprecated is forbidden when active", path)
    if status == "deprecated":
        dep = _exact_keys(ont.get("deprecated"), {"since", "replaced_by", "decision"}, "ont.deprecated", path)
        if not all(_nonempty(dep[key]) for key in dep):
            raise _error("schema", "ont.deprecated values must be non-empty strings", path)
    if ont_type == "concept":
        if "synonyms" in ont:
            _string_list(ont["synonyms"], "synonyms", path)
        if type(ont["relations"]) is not list:
            raise _error("schema", "ont.relations must be a list", path)
        for edge in ont["relations"]:
            edge = _exact_keys(edge, {"type", "target"}, "relation edge", path)
            if not _nonempty(edge["type"]) or not _nonempty(edge["target"]):
                raise _error("schema", "relation edge values must be non-empty strings", path)
        if "system4d" in front:
            system4d = _exact_keys(front["system4d"], {"fog"}, "system4d", path)
            fog = _exact_keys(system4d["fog"], {"risks", "assumptions", "exceptions", "debt"}, "system4d.fog", path)
            for key, value in fog.items():
                _string_list(value, f"system4d.fog.{key}", path)
    else:
        if not _nonempty(ont["group"]):
            raise _error("schema", "ont.group must be a non-empty string", path)
        chars = _exact_keys(ont["characteristics"], {"transitive", "symmetric"}, "ont.characteristics", path)
        if any(type(value) is not bool for value in chars.values()):
            raise _error("schema", "relation characteristics must be booleans", path)
        if type(ont["axis_default"]) is not str or ont["axis_default"] not in ("parents", "children", "left"):
            raise _error("schema", "ont.axis_default is invalid", path)
        if "inverse" in ont and not _nonempty(ont["inverse"]):
            raise _error("schema", "ont.inverse must be a non-empty relation-label string", path)
    return ont, ont_type


def _validate_identity_and_lifecycle(ont: dict[str, Any], kind: str, logical_path: str) -> None:
    if not _safe_logical_path(logical_path):
        raise _error("identity", "logical path is not normalized safe POSIX", logical_path)
    pure = PurePosixPath(logical_path)
    expected_parent = ("reference", "concepts" if kind == "concept" else "relations")
    if tuple(pure.parts[:-1]) != expected_parent or pure.suffix != ".md":
        raise _error("identity", "document is outside its direct-child kind directory", logical_path)
    if _ID_RE.fullmatch(ont["id"]) is None:
        raise _error("identity", "ont.id is invalid", logical_path)
    expected_name = f"{ont['id']}.md" if kind == "concept" else f"{ont['labels'][0]}.md"
    if kind == "relation" and _TOKEN_RE.fullmatch(ont["labels"][0]) is None:
        raise _error("identity", "primary relation label is not a path token", logical_path)
    if pure.name != expected_name or ont["type"] != kind:
        raise _error("identity", "ont identity/type does not match the exact source path", logical_path)
    if ont.get("status", "active") == "deprecated":
        dep = ont["deprecated"]
        try:
            parsed = date.fromisoformat(dep["since"])
        except ValueError as exc:
            raise _error("reference", "ont.deprecated.since is not a valid zero-padded Gregorian date", logical_path) from exc
        if _DATE_RE.fullmatch(dep["since"]) is None or parsed.isoformat() != dep["since"]:
            raise _error("reference", "ont.deprecated.since is not a valid zero-padded Gregorian date", logical_path)
        if not _decision_ref_ok(dep["decision"]):
            raise _error("reference", "ont.deprecated.decision is not an https URL or safe repository path", logical_path)


def parse_ontology_markdown_v1(
    raw: bytes, logical_path: str, *, operation_max_depth: int = MAX_COLLECTION_DEPTH,
    operation_max_items: int = MAX_COLLECTION_ITEMS, defer_placeholder: bool = False,
) -> ParsedSourceDocument:
    """Parse one exact v1 document through the sole v1 grammar implementation."""
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise _error("resource", "ontology document exceeds 1 MiB", logical_path)
    if raw.startswith(b"\xef\xbb\xbf"):
        raise _error("envelope", "UTF-8 BOM is forbidden", logical_path)
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise _error("envelope", "ontology document is not strict UTF-8", logical_path) from exc
    if not text.startswith("---\n"):
        raise _error("envelope", "document must begin with exact ---\\n", logical_path)
    end = text.find("\n---\n", 4)
    if end < 0:
        raise _error("envelope", "document has no exact frontmatter closing delimiter", logical_path)
    front_text = text[4:end]
    front, items = _yaml_value(
        front_text, path=logical_path,
        max_depth=min(MAX_COLLECTION_DEPTH, max(0, operation_max_depth)),
        max_items=min(MAX_COLLECTION_ITEMS, max(0, operation_max_items)),
    )
    ont, kind = _validate_schema(front, path=logical_path)
    _validate_identity_and_lifecycle(ont, kind, logical_path)
    if not defer_placeholder and _PLACEHOLDER_RE.search(text):
        raise _error("placeholder", "placeholder token is forbidden in a v1 document", logical_path)
    return ParsedSourceDocument(raw, text, front, text[end + 5 :], logical_path, kind, items)


def dispatch_source_document(
    source_contract: str | None, raw: bytes, logical_path: str, *,
    legacy_parser: Callable[[bytes, str], Any], operation_max_depth: int = MAX_COLLECTION_DEPTH,
    operation_max_items: int = MAX_COLLECTION_ITEMS, defer_placeholder: bool = False,
) -> Any:
    """Dispatch one document without changing selector-off legacy behavior."""
    if source_contract is None:
        return legacy_parser(raw, logical_path)
    if source_contract != SOURCE_CONTRACT_V1:
        raise SourceContractSelectorError(f"unsupported source contract: {source_contract!r}")
    return parse_ontology_markdown_v1(
        raw, logical_path, operation_max_depth=operation_max_depth,
        operation_max_items=operation_max_items, defer_placeholder=defer_placeholder,
    )


def _doc_path(doc: Any) -> str:
    return str(getattr(doc, "logical_path", None) or getattr(doc, "path", ""))


def validate_resolved_corpus(documents: Iterable[Any]) -> None:
    """Apply v1 uniqueness, lifecycle, reference, inverse, and placeholder rules."""
    docs = list(documents)
    v1 = [doc for doc in docs if getattr(doc, "source_contract", None) == SOURCE_CONTRACT_V1]
    if not v1:
        return
    errors: list[SourceContractError] = []
    by_id: dict[str, list[Any]] = {}
    concepts: dict[str, Any] = {}
    relations: dict[str, Any] = {}
    labels: dict[str, list[Any]] = {}
    for doc in docs:
        ont = getattr(doc, "ont", {})
        ont = ont() if callable(ont) else ont
        ont_id = str(ont.get("id") or "") if type(ont) is dict else ""
        kind = str(ont.get("type") or "") if type(ont) is dict else ""
        if ont_id:
            by_id.setdefault(ont_id, []).append(doc)
            (concepts if kind == "concept" else relations if kind == "relation" else {}).setdefault(ont_id, doc)
        if kind == "relation" and type(ont.get("labels")) is list:
            for label in ont["labels"]:
                if type(label) is str:
                    labels.setdefault(label, []).append(doc)
    for ont_id, matches in by_id.items():
        if len(matches) != 1:
            errors.append(_error("identity", f"ontology id is not unique across the resolved corpus: {ont_id!r}", _doc_path(matches[0])))
    for label, matches in labels.items():
        if len(matches) != 1:
            errors.append(_error("identity", f"relation label is not corpus-wide unique: {label!r}", _doc_path(matches[0])))
    if errors:
        raise sorted(errors, key=lambda exc: (exc.precedence, exc.path or "", exc.message))[0]
    for doc in v1:
        ont = getattr(doc, "ont", {})
        ont = ont() if callable(ont) else ont
        path = _doc_path(doc)
        kind = ont["type"]
        if ont.get("status", "active") == "deprecated":
            replacement = ont["deprecated"]["replaced_by"]
            target = concepts.get(replacement) if kind == "concept" else relations.get(replacement)
            if replacement == ont["id"] or target is None:
                errors.append(_error("reference", "deprecated.replaced_by must resolve to a different same-kind id", path))
        if kind == "concept":
            for edge in ont["relations"]:
                if len(labels.get(edge["type"], ())) != 1:
                    errors.append(_error("reference", f"relation type label does not resolve uniquely: {edge['type']!r}", path))
                if edge["target"] not in concepts:
                    errors.append(_error("reference", f"relation target concept is missing: {edge['target']!r}", path))
        elif "inverse" in ont:
            matches = labels.get(ont["inverse"], [])
            if len(matches) != 1:
                errors.append(_error("reference", f"inverse label does not resolve uniquely: {ont['inverse']!r}", path))
            else:
                other_ont = getattr(matches[0], "ont", {})
                other_ont = other_ont() if callable(other_ont) else other_ont
                if other_ont.get("inverse") not in ont["labels"]:
                    errors.append(_error("reference", "inverse relation is not reciprocal", path))
    if errors:
        raise sorted(errors, key=lambda exc: (exc.precedence, exc.path or "", exc.message))[0]
    for doc in sorted(v1, key=_doc_path):
        raw = getattr(doc, "raw", b"")
        text = raw.decode("utf-8", "strict") if type(raw) is bytes else str(raw)
        if _PLACEHOLDER_RE.search(text):
            raise _error("placeholder", "placeholder token is forbidden in a v1 document", _doc_path(doc))


def classify_v1_reference_entry(kind: str, name: str, mode: int) -> bool:
    """Return whether a direct entry is a document; excluded README returns false."""
    logical = f"reference/{kind}/{name}"
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _error("identity", "v1 reference directories admit regular direct-child files only", logical)
    if name == "README.md":
        return False
    if not name.endswith(".md"):
        raise _error("identity", "unexpected non-Markdown file in a v1 reference directory", logical)
    if not _safe_logical_path(logical):
        raise _error("identity", "v1 reference path is not normalized safe POSIX", logical)
    return True


def iter_v1_reference_paths(src_root: Path) -> list[Path]:
    paths: list[Path] = []
    for kind in ("concepts", "relations"):
        directory = src_root / "reference" / kind
        if not directory.exists() and not directory.is_symlink():
            continue
        try:
            directory_mode = os.lstat(directory).st_mode
        except OSError as exc:
            raise _error("identity", "v1 reference directory is unavailable", f"reference/{kind}") from exc
        if stat.S_ISLNK(directory_mode) or not stat.S_ISDIR(directory_mode):
            raise _error("identity", "v1 reference directory is not a regular directory", f"reference/{kind}")
        for entry in sorted(os.scandir(directory), key=lambda item: os.fsencode(item.name)):
            if classify_v1_reference_entry(kind, entry.name, entry.stat(follow_symlinks=False).st_mode):
                paths.append(Path(entry.path))
    return paths


def source_contract_from_manifest_bytes(raw: bytes) -> str | None:
    try:
        text = raw.decode("utf-8", "strict")
        manifest = yaml.load(text, Loader=_StrictLoader) or {}
    except (UnicodeError, yaml.YAMLError, SourceContractError) as exc:
        raise SourceContractSelectorError(f"invalid adjacent ontology manifest: {exc}") from exc
    if type(manifest) is not dict:
        raise SourceContractSelectorError("adjacent ontology manifest root must be a mapping")
    rocs = manifest.get("rocs")
    if rocs is None:
        return None
    if type(rocs) is not dict:
        raise SourceContractSelectorError("adjacent manifest rocs must be a mapping")
    selector = rocs.get("source_contract")
    if selector is None:
        return None
    if type(selector) is not str or selector != SOURCE_CONTRACT_V1:
        raise SourceContractSelectorError(f"unsupported source contract selector: {selector!r}")
    return selector


def source_contract_for_src_root(src_root: Path) -> str | None:
    manifest = src_root.parent / "manifest.yaml"
    if not manifest.exists() and not manifest.is_symlink():
        return None
    mode = os.lstat(manifest).st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise SourceContractSelectorError("adjacent ontology manifest must be a regular non-symlink file")
    return source_contract_from_manifest_bytes(manifest.read_bytes())


def source_contract_conformance(
    documents: Iterable[Any], layers: Iterable[Any], *, operation: str,
    complete_success: bool, resource_exhausted: bool = False,
) -> dict[str, Any] | None:
    """Return an exact, operation-qualified claim only after complete success."""
    if operation == "context.create" or not complete_success or resource_exhausted:
        return None
    if operation not in INTERPRETING_OPERATIONS:
        raise ValueError(f"operation is not a declared interpreting source reader: {operation}")
    layer_rows = [{
        "name": str(layer.name), "kind": str(layer.kind), "origin": str(layer.origin),
        "source_contract": getattr(layer, "source_contract", None) or "legacy",
    } for layer in layers]
    if not any(row["source_contract"] == SOURCE_CONTRACT_V1 for row in layer_rows):
        return None
    entries = []
    for doc in documents:
        raw = getattr(doc, "raw", None)
        if type(raw) is not bytes:
            continue
        entries.append({
            "layer": str(getattr(doc, "layer_name", None) or getattr(doc, "layer", "")),
            "logical_path": _doc_path(doc), "kind": str(getattr(doc, "ont_type", None) or getattr(doc, "kind", "")),
            "document_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        })
    preimage = {"layers": sorted(layer_rows, key=lambda row: row["name"]), "documents": sorted(entries, key=lambda row: (row["layer"], row["logical_path"]))}
    from rocs_cli.semantic_protocol import jcs_bytes
    return {
        "schema": "rocs-source-contract-conformance.v1",
        "operation": operation,
        "scope": "source-contract/schema/reference",
        "source_contract": SOURCE_CONTRACT_V1,
        "corpus_digest": "sha256:" + hashlib.sha256(jcs_bytes(preimage)).hexdigest(),
        "document_count": len(entries),
        "complete": True,
    }

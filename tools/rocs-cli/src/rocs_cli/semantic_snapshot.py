"""Immutable, no-follow, two-pass corpus capture for semantic discovery."""
from __future__ import annotations

import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from yaml.events import MappingEndEvent, MappingStartEvent, SequenceEndEvent, SequenceStartEvent
from yaml.nodes import MappingNode, Node, SequenceNode

from rocs_cli.layers import LayerSpec
from rocs_cli.semantic_protocol import document_digest, jcs_bytes, object_digest, strict_json_loads, validate_invariants
from rocs_cli.source_contract import (
    SOURCE_CONTRACT_V1,
    ParsedSourceDocument,
    SourceContractError,
    SourceContractSelectorError,
    classify_v1_reference_entry,
    dispatch_source_document,
    source_contract_from_manifest_bytes,
    validate_resolved_corpus,
)
from rocs_cli.workspace import git_head_sha


class SnapshotError(ValueError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class DiscoveryDocument:
    ont_id: str
    kind: str
    layer: str
    layer_order: int
    logical_path: str
    raw: bytes
    document_digest: str
    labels: tuple[str, ...]
    synonyms: tuple[str, ...]
    description: str
    relations: tuple[str, ...]
    examples: tuple[str, ...]
    anti_examples: tuple[str, ...]
    ont: dict[str, Any] | None = None
    source_contract: str | None = None


@dataclass(frozen=True)
class CapturedCorpus:
    snapshot_bytes: bytes
    documents: tuple[DiscoveryDocument, ...]

    @property
    def snapshot(self) -> dict[str, Any]:
        value = strict_json_loads(self.snapshot_bytes)
        if type(value) is not dict:
            raise SnapshotError("internal", "captured snapshot is not an object")
        return value

    @property
    def corpus_snapshot_digest(self) -> str:
        return str(self.snapshot["corpus_snapshot_digest"])


@dataclass(frozen=True)
class _CapturedFile:
    layer: str
    layer_order: int
    logical_path: str
    kind: str
    raw: bytes
    document_digest: str
    source_contract: str | None = None


@dataclass(frozen=True)
class _Generation:
    snapshot_bytes: bytes
    files: tuple[_CapturedFile, ...]
    documents: tuple[DiscoveryDocument, ...]


_STAT_FIELDS = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
_ONT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")
_CONCEPT_KEYS = {"id", "type", "labels", "synonyms", "description", "status", "deprecated", "lint_ignore", "relations", "examples", "anti_examples"}
_RELATION_KEYS = {"id", "type", "labels", "description", "status", "deprecated", "group", "characteristics", "axis_default", "inverse", "lint_ignore"}
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return all(getattr(left, field) == getattr(right, field) for field in _STAT_FIELDS)


def _safe_parts(path: Path) -> tuple[str, ...]:
    absolute = path.absolute()
    if not absolute.is_absolute() or any(part in ("", ".", "..") for part in absolute.parts[1:]):
        raise SnapshotError("invalid_ontology", "invalid corpus root")
    return tuple(absolute.parts[1:])


def _open_anchored_directory(path: Path) -> int:
    fd = os.open("/", _DIR_FLAGS)
    try:
        for part in _safe_parts(path):
            child = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except (OSError, UnicodeError) as exc:
        os.close(fd)
        raise SnapshotError("invalid_ontology", "corpus root is unavailable or unsafe") from exc


def _open_dir_chain(root_fd: int, parts: tuple[str, ...], *, optional: bool = False) -> int | None:
    fd = os.dup(root_fd)
    try:
        for part in parts:
            child = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except FileNotFoundError:
        os.close(fd)
        if optional:
            return None
        raise SnapshotError("invalid_ontology", "required corpus directory is missing") from None
    except OSError as exc:
        os.close(fd)
        raise SnapshotError("invalid_ontology", "corpus directory is unsafe") from exc


def _read_file_at(directory_fd: int, name: str, *, file_limit: int, remaining_bytes: list[int]) -> bytes:
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise SnapshotError("invalid_ontology", "corpus entry is not a regular file")
        if before.st_nlink != 1:
            raise SnapshotError("invalid_ontology", "corpus entry has an unsupported alias")
        if before.st_size > file_limit:
            raise SnapshotError("resource_exhausted", "corpus file byte limit exceeded")
        if before.st_size > remaining_bytes[0]:
            raise SnapshotError("resource_exhausted", "corpus byte limit exceeded")
        fd = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
        try:
            opened = os.fstat(fd)
            if not _same_stat(before, opened):
                raise SnapshotError("snapshot_changed", "corpus changed during capture")
            chunks: list[bytes] = []
            remaining = min(file_limit, remaining_bytes[0])
            while remaining:
                chunk = os.read(fd, min(remaining, 65_536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after_open = os.fstat(fd)
        finally:
            os.close(fd)
        after_path = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except SnapshotError:
        raise
    except OSError as exc:
        raise SnapshotError("snapshot_changed", "corpus changed during capture") from exc
    if len(raw) > file_limit:
        raise SnapshotError("resource_exhausted", "corpus file byte limit exceeded")
    if len(raw) > remaining_bytes[0]:
        raise SnapshotError("resource_exhausted", "corpus byte limit exceeded")
    if not _same_stat(before, after_open) or not _same_stat(before, after_path):
        raise SnapshotError("snapshot_changed", "corpus changed during capture")
    remaining_bytes[0] -= len(raw)
    return raw


def _scan_tree(
    directory_fd: int,
    prefix: PurePosixPath,
    *,
    suffix: str,
    layer: str,
    layer_order: int,
    kind: str | None,
    file_limit: int,
    remaining_files: list[int],
    remaining_bytes: list[int],
) -> list[_CapturedFile]:
    before = os.fstat(directory_fd)
    found: list[_CapturedFile] = []
    try:
        entries = sorted(os.scandir(directory_fd), key=lambda entry: os.fsencode(entry.name))
    except OSError as exc:
        raise SnapshotError("snapshot_changed", "corpus changed during enumeration") from exc
    for entry in entries:
        if any(0xD800 <= ord(character) <= 0xDFFF for character in entry.name):
            raise SnapshotError("invalid_ontology", "corpus path is not valid Unicode")
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise SnapshotError("snapshot_changed", "corpus changed during enumeration") from exc
        if stat.S_ISLNK(info.st_mode):
            raise SnapshotError("invalid_ontology", "corpus contains a symbolic link")
        logical = prefix / entry.name
        if stat.S_ISDIR(info.st_mode):
            child = _open_dir_chain(directory_fd, (entry.name,))
            assert child is not None
            try:
                found.extend(_scan_tree(
                    child, logical, suffix=suffix, layer=layer, layer_order=layer_order,
                    kind=kind, file_limit=file_limit, remaining_files=remaining_files,
                    remaining_bytes=remaining_bytes,
                ))
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode) and entry.name.endswith(suffix):
            if kind is None and entry.name == "README.md":
                continue
            if remaining_files[0] <= 0:
                raise SnapshotError("resource_exhausted", "corpus file count limit exceeded")
            raw = _read_file_at(directory_fd, entry.name, file_limit=file_limit, remaining_bytes=remaining_bytes)
            remaining_files[0] -= 1
            actual_kind = kind
            if actual_kind is None:
                if "/concepts/" in f"/{logical.as_posix()}":
                    actual_kind = "concept"
                elif "/relations/" in f"/{logical.as_posix()}":
                    actual_kind = "relation"
                else:
                    raise SnapshotError("invalid_ontology", "ontology document is outside concepts or relations")
            found.append(_CapturedFile(
                layer=layer, layer_order=layer_order, logical_path=logical.as_posix(),
                kind=actual_kind, raw=raw, document_digest=document_digest(raw),
            ))
        elif not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
            raise SnapshotError("invalid_ontology", "corpus contains an unsupported entry")
    after = os.fstat(directory_fd)
    if not _same_stat(before, after):
        raise SnapshotError("snapshot_changed", "corpus changed during enumeration")
    return found


def _scan_v1_kind(
    directory_fd: int,
    prefix: PurePosixPath,
    *,
    layer: str,
    layer_order: int,
    kind: str,
    file_limit: int,
    remaining_files: list[int],
    remaining_bytes: list[int],
) -> list[_CapturedFile]:
    before = os.fstat(directory_fd)
    found: list[_CapturedFile] = []
    try:
        entries = sorted(os.scandir(directory_fd), key=lambda entry: os.fsencode(entry.name))
    except OSError as exc:
        raise SnapshotError("snapshot_changed", "corpus changed during enumeration") from exc
    for entry in entries:
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
            selected = classify_v1_reference_entry(kind, entry.name, mode)
        except SourceContractError as exc:
            raise SnapshotError(exc.kind, "v1 reference membership is invalid") from exc
        except OSError as exc:
            raise SnapshotError("snapshot_changed", "corpus changed during enumeration") from exc
        if not selected:
            continue
        if remaining_files[0] <= 0:
            raise SnapshotError("resource_exhausted", "corpus file count limit exceeded")
        raw = _read_file_at(directory_fd, entry.name, file_limit=file_limit, remaining_bytes=remaining_bytes)
        remaining_files[0] -= 1
        logical = (prefix / entry.name).as_posix()
        found.append(_CapturedFile(
            layer, layer_order, logical, "concept" if kind == "concepts" else "relation",
            raw, document_digest(raw), SOURCE_CONTRACT_V1,
        ))
    if not _same_stat(before, os.fstat(directory_fd)):
        raise SnapshotError("snapshot_changed", "corpus changed during enumeration")
    return found


def _yaml_value(raw: bytes, *, max_depth: int, item_budget: list[int]) -> Any:
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise SnapshotError("invalid_ontology", "corpus content is not valid UTF-8 YAML") from exc

    # Stream events first so hostile nesting is bounded before node composition recurses.
    depth = 0
    try:
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, (MappingStartEvent, SequenceStartEvent)):
                depth += 1
                if depth > max_depth:
                    raise SnapshotError("resource_exhausted", "parser depth limit exceeded")
            elif isinstance(event, (MappingEndEvent, SequenceEndEvent)):
                depth -= 1
    except SnapshotError:
        raise
    except (yaml.YAMLError, RecursionError) as exc:
        raise SnapshotError("resource_exhausted", "parser depth limit exceeded") from exc

    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except RecursionError as exc:
        raise SnapshotError("resource_exhausted", "parser depth limit exceeded") from exc
    except yaml.YAMLError as exc:
        raise SnapshotError("invalid_ontology", "corpus content is not valid YAML") from exc
    stack: set[int] = set()

    def visit(current: Node | None, collection_depth: int) -> None:
        if current is None or not isinstance(current, (MappingNode, SequenceNode)):
            return
        if collection_depth > max_depth:
            raise SnapshotError("resource_exhausted", "parser depth limit exceeded")
        identity = id(current)
        if identity in stack:
            raise SnapshotError("invalid_ontology", "recursive YAML aliases are forbidden")
        stack.add(identity)
        try:
            children: list[Node] = []
            if isinstance(current, MappingNode):
                item_budget[0] -= len(current.value)
                for key, value in current.value:
                    children.extend((key, value))
            else:
                item_budget[0] -= len(current.value)
                children.extend(current.value)
            if item_budget[0] < 0:
                raise SnapshotError("resource_exhausted", "parser collection limit exceeded")
            for child in children:
                if isinstance(child, (MappingNode, SequenceNode)):
                    visit(child, collection_depth + 1)
        finally:
            stack.remove(identity)

    visit(node, 1)
    try:
        return yaml.safe_load(text)
    except RecursionError as exc:
        raise SnapshotError("resource_exhausted", "parser depth limit exceeded") from exc
    except yaml.YAMLError as exc:
        raise SnapshotError("invalid_ontology", "corpus content is not valid YAML") from exc


def _string_list(value: Any, field: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if type(value) is not list or (required and not value) or any(type(item) is not str or not item.strip() for item in value):
        raise SnapshotError("invalid_ontology", f"ontology {field} must be a non-empty string list" if required else f"ontology {field} must be a string list")
    return tuple(value)


def _parse_legacy_document(captured: _CapturedFile, *, max_depth: int, item_budget: list[int]) -> DiscoveryDocument:
    try:
        text = captured.raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise SnapshotError("invalid_ontology", "ontology document is not valid UTF-8") from exc
    if not text.startswith("---\n"):
        raise SnapshotError("invalid_ontology", "ontology document is missing front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SnapshotError("invalid_ontology", "ontology document has invalid front matter")
    front = _yaml_value(text[4:end].encode("utf-8"), max_depth=max_depth, item_budget=item_budget)
    if type(front) is not dict or set(front) != {"ont"} or type(front.get("ont")) is not dict:
        raise SnapshotError("invalid_ontology", "ontology front matter is invalid")
    ont = front["ont"]
    ont_id, ont_type, description = ont.get("id"), ont.get("type"), ont.get("description")
    if type(ont_id) is not str or _ONT_ID_RE.fullmatch(ont_id) is None:
        raise SnapshotError("invalid_ontology", "ontology identity is invalid")
    if type(ont_type) is not str or type(description) is not str or not description.strip():
        raise SnapshotError("invalid_ontology", "ontology type and description must be non-empty strings")
    if ont_type != captured.kind:
        raise SnapshotError("invalid_ontology", "ontology type does not match document location")
    if set(ont) - (_CONCEPT_KEYS if ont_type == "concept" else _RELATION_KEYS):
        raise SnapshotError("invalid_ontology", "ontology contains unknown fields")
    status = ont.get("status", "active")
    if status not in ("active", "deprecated"):
        raise SnapshotError("invalid_ontology", "ontology status is invalid")
    if status == "deprecated":
        deprecated = ont.get("deprecated")
        if type(deprecated) is not dict or any(type(deprecated.get(key)) is not str or not deprecated[key].strip() for key in ("since", "replaced_by", "decision")):
            raise SnapshotError("invalid_ontology", "deprecated ontology metadata is incomplete")
    relations_raw = ont.get("relations", [])
    if type(relations_raw) is not list:
        raise SnapshotError("invalid_ontology", "ontology relations must be a list")
    relations: list[str] = []
    for relation in relations_raw:
        if type(relation) is not dict or set(relation) != {"type", "target"} or type(relation.get("type")) is not str or not relation["type"].strip() or type(relation.get("target")) is not str or not relation["target"].strip():
            raise SnapshotError("invalid_ontology", "ontology relation edges must contain only non-empty string type and target")
        relations.extend((relation["type"], relation["target"]))
    return DiscoveryDocument(
        ont_id=ont_id, kind=ont_type, layer=captured.layer, layer_order=captured.layer_order,
        logical_path=captured.logical_path, raw=captured.raw, document_digest=captured.document_digest,
        labels=_string_list(ont.get("labels"), "labels", required=True),
        synonyms=_string_list(ont.get("synonyms"), "synonyms"), description=description,
        relations=tuple(relations), examples=_string_list(ont.get("examples"), "examples"),
        anti_examples=_string_list(ont.get("anti_examples"), "anti_examples"), ont=ont,
    )


def _parse_document(captured: _CapturedFile, *, max_depth: int, item_budget: list[int]) -> DiscoveryDocument:
    try:
        parsed = dispatch_source_document(
            captured.source_contract,
            captured.raw,
            captured.logical_path,
            legacy_parser=lambda _raw, _path: _parse_legacy_document(
                captured, max_depth=max_depth, item_budget=item_budget
            ),
            operation_max_depth=max_depth,
            operation_max_items=max(0, item_budget[0]),
            defer_placeholder=True,
        )
    except SourceContractError as exc:
        raise SnapshotError(exc.kind, "ontology document violates its selected source contract") from exc
    if isinstance(parsed, DiscoveryDocument):
        return parsed
    assert isinstance(parsed, ParsedSourceDocument)
    item_budget[0] -= parsed.collection_items
    ont = parsed.ont
    relations = tuple(
        value
        for edge in ont.get("relations", [])
        for value in (edge["type"], edge["target"])
    )
    return DiscoveryDocument(
        ont_id=parsed.ont_id, kind=parsed.kind, layer=captured.layer, layer_order=captured.layer_order,
        logical_path=captured.logical_path, raw=captured.raw, document_digest=captured.document_digest,
        labels=tuple(ont["labels"]), synonyms=tuple(ont.get("synonyms", [])), description=ont["description"],
        relations=relations, examples=tuple(ont.get("examples", [])), anti_examples=tuple(ont.get("anti_examples", [])),
        ont=ont, source_contract=SOURCE_CONTRACT_V1,
    )


def _validate_layer_origin(layer: LayerSpec) -> None:
    if layer.kind == "path":
        origin = PurePosixPath(layer.origin)
        if origin.is_absolute() or any(part in ("", ".", "..") for part in origin.parts):
            raise SnapshotError("invalid_ontology", "path layer origin is unsafe")


def _capture_generation(layers: list[LayerSpec], profile: str, limits: dict[str, int]) -> _Generation:
    files: list[_CapturedFile] = []
    roots: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    seen_root_paths: set[tuple[int, int]] = set()
    remaining_files = [limits["corpus_files"]]
    remaining_bytes = [limits["corpus_bytes"]]
    for layer_order, layer in enumerate(layers):
        _validate_layer_origin(layer)
        root_fd = _open_anchored_directory(layer.src_root.parent)
        try:
            root_stat = os.fstat(root_fd)
            root_identity = (root_stat.st_dev, root_stat.st_ino)
            if root_identity in seen_root_paths:
                raise SnapshotError("invalid_ontology", "corpus roots alias the same directory")
            seen_root_paths.add(root_identity)
            roots.append({"root_id": layer.name, "layer": layer.name, "layer_order": layer_order, "kind": layer.kind})
            if layer.kind == "ref":
                revision = git_head_sha(layer.src_root.parent)
                if revision is None:
                    raise SnapshotError("invalid_ontology", "resolved ref revision is unavailable")
                refs.append({"layer": layer.name, "layer_order": layer_order, "locator": layer.origin, "resolved_revision": revision})
            try:
                if remaining_files[0] <= 0:
                    raise SnapshotError("resource_exhausted", "corpus file count limit exceeded")
                manifest_raw = _read_file_at(
                    root_fd, "manifest.yaml", file_limit=limits["file_bytes"], remaining_bytes=remaining_bytes,
                )
                remaining_files[0] -= 1
            except SnapshotError as exc:
                if exc.kind == "snapshot_changed":
                    raise SnapshotError("invalid_ontology", "ontology manifest is unavailable") from exc
                raise
            try:
                selected_contract = source_contract_from_manifest_bytes(manifest_raw)
            except SourceContractSelectorError as exc:
                raise SnapshotError("invalid_ontology", "ontology source contract selector is invalid") from exc
            if layer.source_contract is not None and layer.source_contract != selected_contract:
                raise SnapshotError("snapshot_changed", "ontology source contract selector changed during capture")
            files.append(_CapturedFile(layer.name, layer_order, "manifest.yaml", "manifest", manifest_raw, document_digest(manifest_raw)))
            profiles_fd = _open_dir_chain(root_fd, ("profiles",), optional=True)
            if profiles_fd is not None:
                try:
                    files.extend(_scan_tree(
                        profiles_fd, PurePosixPath("profiles"), suffix=".yaml", layer=layer.name,
                        layer_order=layer_order, kind="profile", file_limit=limits["file_bytes"],
                        remaining_files=remaining_files, remaining_bytes=remaining_bytes,
                    ))
                finally:
                    os.close(profiles_fd)
            source_rel = layer.src_root.absolute().relative_to(layer.src_root.parent.absolute())
            if selected_contract == SOURCE_CONTRACT_V1:
                for reference_kind in ("concepts", "relations"):
                    reference_fd = _open_dir_chain(
                        root_fd,
                        tuple(source_rel.parts) + ("reference", reference_kind),
                        optional=True,
                    )
                    if reference_fd is not None:
                        try:
                            files.extend(_scan_v1_kind(
                                reference_fd,
                                PurePosixPath("reference") / reference_kind,
                                layer=layer.name,
                                layer_order=layer_order,
                                kind=reference_kind,
                                file_limit=limits["file_bytes"],
                                remaining_files=remaining_files,
                                remaining_bytes=remaining_bytes,
                            ))
                        finally:
                            os.close(reference_fd)
            else:
                reference_fd = _open_dir_chain(root_fd, tuple(source_rel.parts) + ("reference",), optional=True)
                if reference_fd is not None:
                    try:
                        files.extend(_scan_tree(
                            reference_fd, PurePosixPath("reference"), suffix=".md", layer=layer.name,
                            layer_order=layer_order, kind=None, file_limit=limits["file_bytes"],
                            remaining_files=remaining_files, remaining_bytes=remaining_bytes,
                        ))
                    finally:
                        os.close(reference_fd)
            if not _same_stat(root_stat, os.fstat(root_fd)):
                raise SnapshotError("snapshot_changed", "corpus root changed during capture")
        finally:
            os.close(root_fd)
    item_budget = [limits["collection_items"]]
    for item in files:
        if item.kind in ("manifest", "profile"):
            _yaml_value(item.raw, max_depth=limits["parser_depth"], item_budget=item_budget)
    documents = tuple(
        _parse_document(item, max_depth=limits["parser_depth"], item_budget=item_budget)
        for item in files if item.kind in ("concept", "relation")
    )
    try:
        validate_resolved_corpus(documents)
    except SourceContractError as exc:
        raise SnapshotError(exc.kind, "resolved corpus violates its selected source contract") from exc
    identities = [(document.ont_id, document.kind) for document in documents]
    if len(identities) != len(set(identities)):
        raise SnapshotError("invalid_ontology", "duplicate ontology semantic identity")
    concept_ids = {document.ont_id for document in documents if document.kind == "concept"}
    relation_labels: dict[str, str] = {}
    for document in documents:
        if document.kind == "relation":
            for label in document.labels:
                if label in relation_labels:
                    raise SnapshotError("invalid_ontology", "relation label collision")
                relation_labels[label] = document.ont_id
    for document in documents:
        if document.kind == "concept":
            for index in range(0, len(document.relations), 2):
                relation_type, target = document.relations[index:index + 2]
                if relation_type not in relation_labels or target not in concept_ids:
                    raise SnapshotError("invalid_ontology", "ontology relation edge is unresolved")
    logical = [(item.layer, unicodedata.normalize("NFC", item.logical_path)) for item in files]
    if any(normalized != item.logical_path for item, (_, normalized) in zip(files, logical)) or len(logical) != len(set(logical)):
        raise SnapshotError("invalid_ontology", "logical path normalization collision")
    files.sort(key=lambda item: (item.layer_order, item.logical_path.encode(), item.kind))
    entries = [{
        "logical_path": item.logical_path, "layer": item.layer, "layer_order": item.layer_order,
        "kind": item.kind, "raw_byte_length": len(item.raw), "document_digest": item.document_digest,
    } for item in files]
    snapshot: dict[str, Any] = {
        "schema": "semantic-corpus-snapshot.v0", "profile": profile, "roots": roots,
        "resolved_refs": refs, "entries": entries,
    }
    snapshot["corpus_snapshot_digest"] = object_digest("corpus_snapshot", snapshot)
    failures = validate_invariants(snapshot)
    if failures:
        raise SnapshotError("invalid_ontology", "captured corpus violates snapshot invariants")
    return _Generation(jcs_bytes(snapshot), tuple(files), documents)


def capture_corpus(layers: list[LayerSpec], *, profile: str, limits: dict[str, int]) -> CapturedCorpus:
    if not layers:
        raise SnapshotError("invalid_ontology", "semantic discovery requires at least one layer")
    first = _capture_generation(layers, profile, limits)
    second = _capture_generation(layers, profile, limits)
    if first.snapshot_bytes != second.snapshot_bytes or first.files != second.files or first.documents != second.documents:
        raise SnapshotError("snapshot_changed", "corpus changed between capture passes")
    return CapturedCorpus(snapshot_bytes=first.snapshot_bytes, documents=first.documents)

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, replace
from pathlib import Path

from rocs_cli.frontmatter import split_frontmatter
from rocs_cli.layers import LayerSpec
from rocs_cli.source_contract import (
    MAX_DOCUMENT_BYTES,
    SOURCE_CONTRACT_V1,
    ParsedSourceDocument,
    SourceContractError,
    SourceContractSelectorError,
    dispatch_source_document,
    iter_v1_reference_paths,
    source_contract_for_src_root,
    validate_resolved_corpus,
)


@dataclass(frozen=True)
class OntDoc:
    path: Path
    fm: dict
    body: str
    layer_name: str
    layer_kind: str  # path|ref
    raw: bytes | None = None
    logical_path: str | None = None
    source_contract: str | None = None

    @property
    def ont(self) -> dict:
        ont = self.fm.get("ont")
        if isinstance(ont, dict):
            return ont
        return {}

    @property
    def ont_id(self) -> str:
        return str(self.ont.get("id") or "")

    @property
    def ont_type(self) -> str:
        return str(self.ont.get("type") or "")


def iter_reference_md(src_root: Path) -> list[Path]:
    """Legacy recursive membership, retained only when the selector is absent."""
    ref = src_root / "reference"
    out: list[Path] = []
    if not ref.exists():
        return out
    for path in sorted(ref.rglob("*.md")):
        if path.name != "README.md":
            out.append(path)
    return out


def iter_layer_reference_md(layer: LayerSpec) -> list[Path]:
    if layer.source_contract == SOURCE_CONTRACT_V1:
        return iter_v1_reference_paths(layer.src_root)
    return iter_reference_md(layer.src_root)


def iter_md(src_root: Path) -> list[Path]:
    out: list[Path] = []
    if src_root.exists():
        out.extend(sorted(src_root.rglob("*.md")))
    return out


def _legacy_document(raw: bytes, logical_path: str) -> tuple[dict, str]:
    try:
        text = raw.decode("utf-8", "strict")
        fm, body = split_frontmatter(text)
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid UTF-8: {logical_path}") from exc
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"invalid front matter YAML: {logical_path}: {exc}") from exc
    if fm is None:
        raise ValueError(f"missing front matter: {logical_path}")
    if not isinstance(fm, dict):
        raise ValueError(f"front matter must be a mapping: {logical_path}")
    ont = fm.get("ont")
    if ont is not None and not isinstance(ont, dict):
        raise ValueError(f"front matter ont must be a mapping: {logical_path}")
    return fm, body


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev, value.st_ino, value.st_mode, value.st_size,
        value.st_mtime_ns, value.st_ctime_ns,
    )


def _read_v1(path: Path, logical_path: str) -> bytes:
    before = os.lstat(path)
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise SourceContractError("identity", "v1 document must be a regular non-symlink file", path=logical_path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if _file_identity(before) != _file_identity(opened):
            raise SourceContractError("identity", "v1 document changed during admission", path=logical_path)
        if opened.st_size > MAX_DOCUMENT_BYTES:
            raise SourceContractError(
                "resource", "ontology document exceeds 1 MiB", path=logical_path,
                kind="resource_exhausted",
            )
        chunks: list[bytes] = []
        remaining = MAX_DOCUMENT_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise SourceContractError(
                "resource", "ontology document exceeds 1 MiB", path=logical_path,
                kind="resource_exhausted",
            )
        after = os.fstat(fd)
        if _file_identity(opened) != _file_identity(after) or len(raw) != after.st_size:
            raise SourceContractError("identity", "v1 document changed during admission", path=logical_path)
        return raw
    finally:
        os.close(fd)


def load_doc(path: Path, *, layer: LayerSpec) -> OntDoc:
    logical_path = path.relative_to(layer.src_root).as_posix()
    raw = _read_v1(path, logical_path) if layer.source_contract == SOURCE_CONTRACT_V1 else path.read_bytes()
    parsed = dispatch_source_document(
        layer.source_contract,
        raw,
        logical_path,
        legacy_parser=_legacy_document,
        defer_placeholder=True,
    )
    if isinstance(parsed, ParsedSourceDocument):
        fm, body = parsed.frontmatter, parsed.body
    else:
        fm, body = parsed
    return OntDoc(
        path=path,
        fm=fm,
        body=body,
        layer_name=layer.name,
        layer_kind=layer.kind,
        raw=raw,
        logical_path=logical_path,
        source_contract=layer.source_contract,
    )


def _effective_layers(layers: list[LayerSpec]) -> list[LayerSpec]:
    effective: list[LayerSpec] = []
    for layer in layers:
        try:
            selected = source_contract_for_src_root(layer.src_root)
        except (OSError, UnicodeError, SourceContractSelectorError) as exc:
            raise ValueError(f"invalid source contract selector for layer {layer.name!r}: {exc}") from exc
        if layer.source_contract is not None and selected != layer.source_contract:
            raise ValueError(f"source contract selector changed during admission for layer {layer.name!r}")
        effective.append(layer if selected == layer.source_contract else replace(layer, source_contract=selected))
    return effective


def _index_documents(documents: list[OntDoc], *, strict_v1: bool) -> tuple[dict[str, OntDoc], dict[str, OntDoc]]:
    concepts: dict[str, OntDoc] = {}
    relations: dict[str, OntDoc] = {}
    for doc in documents:
        destination = concepts if doc.ont_type == "concept" else relations if doc.ont_type == "relation" else None
        if destination is None:
            raise SystemExit(f"unknown ont.type in {doc.path}: {doc.ont_type!r}")
        if doc.ont_id in destination:
            kind = "concept" if destination is concepts else "relation"
            raise SystemExit(
                f"duplicate {kind} id {doc.ont_id!r} in {doc.path} (already in {destination[doc.ont_id].path})"
            )
        destination[doc.ont_id] = doc
    return concepts, relations


def collect_docs(layers: list[LayerSpec]) -> tuple[dict[str, OntDoc], dict[str, OntDoc]]:
    effective = _effective_layers(layers)
    has_v1 = any(layer.source_contract == SOURCE_CONTRACT_V1 for layer in effective)

    # The legacy cache remains byte-for-byte compatible.  V1 always re-admits the
    # exact current bytes through the shared parser, so a parsed cache cannot bypass it.
    if not has_v1:
        from rocs_cli.index_cache import collect_docs_cached, index_cache_enabled  # noqa: PLC0415

        if index_cache_enabled():
            return collect_docs_cached(effective)

    documents = [
        load_doc(path, layer=layer)
        for layer in effective
        for path in iter_layer_reference_md(layer)
    ]
    if has_v1:
        validate_resolved_corpus(documents)
    return _index_documents(documents, strict_v1=has_v1)


def relation_label_index(relations: dict[str, OntDoc]) -> dict[str, set[str]]:
    rel_label_to_ids: dict[str, set[str]] = {}
    for rid, rdoc in relations.items():
        labels = rdoc.ont.get("labels") or []
        for label in labels:
            rel_label_to_ids.setdefault(str(label), set()).add(rid)
    return rel_label_to_ids

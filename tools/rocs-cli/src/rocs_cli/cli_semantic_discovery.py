"""CLI adapters for semantic discovery and snapshot-bound exact-ID packs."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from rocs_cli.discovery import (
    DEFAULT_LIMITS,
    DiscoveryError,
    capabilities,
    discover,
    error_envelope,
    validate_request,
)
from rocs_cli.errors import RocsCliError
from rocs_cli.layers import repo_root as resolve_repo_root, resolve_layers
from rocs_cli.semantic_protocol import (
    caller_request_identity,
    object_digest,
    validate_invariants,
    validate_protocol,
)
from rocs_cli.semantic_snapshot import CapturedCorpus, DiscoveryDocument, SnapshotError, capture_corpus

_MAX_REQUEST_ENVELOPE_BYTES = 262_144


def _console():
    from rocs_cli.cli import console
    return console


def _emit(value: dict[str, Any]) -> None:
    _console().print_json(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _safe_error(kind: str, caller_digest: str | None = None) -> DiscoveryError:
    return DiscoveryError(kind, caller_request_digest=caller_digest)


def _read_request(args: argparse.Namespace) -> tuple[dict[str, Any] | None, str | None]:
    if args.request_json == "-":
        raw = sys.stdin.buffer.read(_MAX_REQUEST_ENVELOPE_BYTES + 1)
    elif args.request_file:
        path = Path(args.request_file)
        try:
            if path.is_symlink() or not path.is_file():
                return None, None
            with path.open("rb") as handle:
                raw = handle.read(_MAX_REQUEST_ENVELOPE_BYTES + 1)
        except OSError:
            return None, None
    else:
        return None, None
    if len(raw) > _MAX_REQUEST_ENVELOPE_BYTES:
        return None, None
    return caller_request_identity(raw)


def _layers(args: argparse.Namespace, *, profile: str) -> tuple[list, dict]:
    repo = resolve_repo_root(args.repo)
    return resolve_layers(
        repo,
        profile=profile,
        resolve_refs=bool(args.resolve_refs),
        workspace_root=args.workspace_root,
        workspace_ref_mode=args.workspace_ref_mode,
    )


def _tool_identity(args: argparse.Namespace) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "kind": args.tool_kind,
        "manifest_digest": args.tool_manifest_digest,
        "python_version": __import__("platform").python_version(),
        "unicode_data": __import__("unicodedata").unidata_version,
    }
    identity["digest"] = object_digest("tool_identity", identity)
    return identity


def cmd_discover_capabilities(_args: argparse.Namespace) -> int:
    payload = capabilities()
    if validate_protocol(payload):
        raise RuntimeError("semantic discovery capabilities violate the protocol")
    _emit(payload)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    caller_digest: str | None = None
    try:
        request, caller_digest = _read_request(args)
        if request is None:
            raise _safe_error("invalid_request")
        caller_digest = validate_request(request)
        digest_pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
        if (
            getattr(args, "parser_unknown", [])
            or not ((args.request_json == "-") ^ bool(args.request_file))
            or not args.repo
            or args.tool_kind not in ("development_runtime", "adopted_runtime")
            or type(args.tool_manifest_digest) is not str
            or digest_pattern.fullmatch(args.tool_manifest_digest) is None
            or not args.json
            or not args.no_index_cache
            or not args.no_env_file
            or args.workspace_ref_mode not in (None, "strict", "loose")
        ):
            raise _safe_error("invalid_request", caller_digest)
        layers, _meta = _layers(args, profile=str(request["profile"]))
        corpus = capture_corpus(layers, profile=str(request["profile"]), limits=request.get("limits", DEFAULT_LIMITS))
        execution = discover(corpus, request, tool_identity=_tool_identity(args))
        _emit(execution.result)
        return 0
    except DiscoveryError as error:
        _emit(error_envelope(error))
        return 1
    except SnapshotError as error:
        _emit(error_envelope(_safe_error(error.kind, caller_digest)))
        return 1
    except RocsCliError:
        _emit(error_envelope(_safe_error("invalid_ontology", caller_digest)))
        return 1
    except Exception:
        _emit(error_envelope(_safe_error("internal", caller_digest)))
        return 1


def _pack_documents(
    corpus: CapturedCorpus,
    *,
    root_id: str,
    max_depth: int,
    rel_types: set[str] | None,
    include_relation_defs: bool,
    max_docs: int,
    max_bytes: int,
) -> list[DiscoveryDocument]:
    concepts = {document.ont_id: document for document in corpus.documents if document.kind == "concept"}
    relations = {document.ont_id: document for document in corpus.documents if document.kind == "relation"}
    root = concepts.get(root_id) or relations.get(root_id)
    if root is None:
        raise _safe_error("invalid_ontology")

    included: set[str] = {root_id} if root.kind == "concept" else set()
    frontier: list[tuple[str, int]] = [(root_id, 0)] if root.kind == "concept" else []
    relation_labels: set[str] = set()
    while frontier:
        current_id, depth = frontier.pop(0)
        current = concepts[current_id]
        edges = list(zip(current.relations[0::2], current.relations[1::2]))
        for relation_type, target in edges:
            if rel_types is None or relation_type in rel_types:
                relation_labels.add(relation_type)
                if depth < max_depth and target in concepts and target not in included:
                    included.add(target)
                    frontier.append((target, depth + 1))

    ordered: list[DiscoveryDocument] = [root]
    if root.kind == "concept":
        ordered.extend(concepts[ont_id] for ont_id in sorted(included) if ont_id != root_id)
    if include_relation_defs:
        by_label = {label: document for document in relations.values() for label in document.labels}
        relation_ids = {by_label[label].ont_id for label in relation_labels if label in by_label}
        ordered.extend(relations[ont_id] for ont_id in sorted(relation_ids) if ont_id != root_id)

    emitted: list[DiscoveryDocument] = []
    used = 0
    for document in ordered:
        size = len(document.raw)
        if not emitted and (max_docs < 1 or size > max_bytes):
            raise _safe_error("resource_exhausted")
        if len(emitted) >= max_docs or used + size > max_bytes:
            break
        emitted.append(document)
        used += size
    return emitted


def cmd_pack_dispatch(args: argparse.Namespace) -> int:
    bound = bool(args.expected_snapshot_digest or args.expected_document_digest)
    if bound:
        if not args.expected_snapshot_digest or not args.expected_document_digest or not args.json or not args.no_env_file or not args.no_index_cache:
            _emit(error_envelope(_safe_error("invalid_request")))
            return 1
        return cmd_bound_pack(args)
    from rocs_cli.cli_ontology_utility import cmd_pack
    return cmd_pack(args)


def cmd_bound_pack(args: argparse.Namespace) -> int:
    try:
        profile = str(args.profile or "")
        digest_pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
        if not profile or re.fullmatch(r"[A-Za-z0-9_-]+", profile) is None:
            raise _safe_error("invalid_request")
        if digest_pattern.fullmatch(args.expected_snapshot_digest) is None or digest_pattern.fullmatch(args.expected_document_digest) is None:
            raise _safe_error("invalid_request")
        if args.depth is not None and not 0 <= args.depth <= 4_294_967_295:
            raise _safe_error("invalid_request")
        if args.max_docs is not None and not 1 <= args.max_docs <= 4_294_967_295:
            raise _safe_error("invalid_request")
        if args.max_bytes is not None and not 1 <= args.max_bytes <= 4_294_967_295:
            raise _safe_error("invalid_request")
        layers, _meta = _layers(args, profile=profile)
        corpus = capture_corpus(layers, profile=profile, limits=dict(DEFAULT_LIMITS))
        if corpus.corpus_snapshot_digest != args.expected_snapshot_digest:
            raise _safe_error("snapshot_changed")
        root = next((document for document in corpus.documents if document.ont_id == args.ont_id), None)
        if root is None:
            raise _safe_error("invalid_ontology")
        if root.document_digest != args.expected_document_digest:
            raise _safe_error("snapshot_changed")
        rel_types = {value.strip() for value in args.rel_types.split(",") if value.strip()} if args.rel_types else None
        if rel_types is not None and any(re.fullmatch(r"[A-Za-z0-9_-]+", value) is None for value in rel_types):
            raise _safe_error("invalid_request")
        max_docs = args.max_docs if args.max_docs is not None else 4_294_967_295
        max_bytes = args.max_bytes if args.max_bytes is not None else 4_294_967_295
        documents = _pack_documents(
            corpus,
            root_id=args.ont_id,
            max_depth=args.depth if args.depth is not None else 0,
            rel_types=rel_types,
            include_relation_defs=bool(args.include_relation_defs),
            max_docs=max_docs,
            max_bytes=max_bytes,
        )
        payload: dict[str, Any] = {
            "schema": "semantic-pack-result.v0",
            "corpus_snapshot_digest": corpus.corpus_snapshot_digest,
            "root_id": root.ont_id,
            "root_document_digest": root.document_digest,
            "config": {
                "max_depth": args.depth if args.depth is not None else 0,
                "rel_types": sorted(rel_types) if rel_types is not None else [],
                "include_relation_defs": bool(args.include_relation_defs),
                "max_docs": max_docs,
                "max_bytes": max_bytes,
            },
            "documents": [{
                "ont_id": document.ont_id,
                "kind": document.kind,
                "logical_path": document.logical_path,
                "document_digest": document.document_digest,
                "text": document.raw.decode("utf-8"),
            } for document in documents],
        }
        payload["pack_digest"] = object_digest("pack", payload)
        if validate_protocol(payload) or validate_invariants(payload):
            raise _safe_error("internal")
        _emit(payload)
        return 0
    except DiscoveryError as error:
        _emit(error_envelope(error))
        return 1
    except SnapshotError as error:
        _emit(error_envelope(_safe_error(error.kind)))
        return 1
    except RocsCliError:
        _emit(error_envelope(_safe_error("invalid_ontology")))
        return 1
    except Exception:
        _emit(error_envelope(_safe_error("internal")))
        return 1

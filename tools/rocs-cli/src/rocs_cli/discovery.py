"""Pure deterministic `rocs-lexical-v0` discovery over an immutable corpus."""
from __future__ import annotations

import platform
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any

from rocs_cli.semantic_protocol import (
    ProtocolError,
    jcs_bytes,
    lexical_tokens,
    normalize_lexical,
    object_digest,
    validate_definition,
    validate_invariants,
    validate_protocol,
    verify_object_digest,
)
from rocs_cli.semantic_snapshot import CapturedCorpus, DiscoveryDocument

DEFAULT_LIMITS = {
    "query_bytes": 16_384,
    "corpus_files": 5_000,
    "corpus_bytes": 33_554_432,
    "file_bytes": 1_048_576,
    "parser_depth": 32,
    "collection_items": 10_000,
    "candidates": 12,
    "result_bytes": 65_536,
}
ALGORITHM = {"id": "rocs-lexical-v0", "unicode_data": "15.0.0"}
_POSITIVE_WEIGHTS = {
    "id": (500, 1000),
    "label": (400, 800),
    "synonym": (350, 700),
    "description": (100, 200),
    "relation": (80, 160),
    "example": (50, 100),
}
_ERROR_MESSAGES = {
    "incompatible": "semantic discovery runtime is incompatible",
    "invalid_request": "semantic discovery request is invalid",
    "invalid_ontology": "semantic discovery corpus is invalid",
    "resource_exhausted": "semantic discovery resource limit exceeded",
    "snapshot_changed": "semantic discovery corpus changed during capture",
    "unsupported_identity": "semantic discovery identity is unsupported",
    "internal": "semantic discovery failed internally",
}


class DiscoveryError(ValueError):
    def __init__(self, kind: str, message: str | None = None, *, caller_request_digest: str | None = None):
        if kind not in _ERROR_MESSAGES:
            kind = "internal"
        safe = message if message in _ERROR_MESSAGES.values() else _ERROR_MESSAGES[kind]
        super().__init__(safe)
        self.kind = kind
        self.message = safe
        self.caller_request_digest = caller_request_digest


@dataclass(frozen=True)
class DiscoveryExecution:
    request: dict[str, Any]
    effective_execution: dict[str, Any]
    result: dict[str, Any]


def capabilities() -> dict[str, Any]:
    return {
        "schema": "semantic-discovery-capabilities.v0",
        "request_schemas": ["semantic-discovery-request.v0"],
        "result_schemas": ["semantic-discovery-result.v0"],
        "pack_schemas": ["semantic-pack-result.v0"],
        "error_schemas": ["rocs-error.v0"],
        "algorithms": ["rocs-lexical-v0"],
        "unicode_data": ["15.0.0"],
        "platforms": ["linux"],
    }


def error_envelope(error: DiscoveryError) -> dict[str, Any]:
    envelope = {
        "ok": False,
        "error": {
            "schema": "rocs-error.v0",
            "kind": error.kind,
            "message": error.message,
            "caller_request_digest": error.caller_request_digest,
        },
    }
    if validate_protocol(envelope):
        raise ProtocolError("internal error envelope violates protocol schema")
    return envelope


def development_tool_identity(*, manifest_digest: str) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "kind": "development_runtime",
        "manifest_digest": manifest_digest,
        "python_version": platform.python_version(),
        "unicode_data": unicodedata.unidata_version,
    }
    identity["digest"] = object_digest("tool_identity", identity)
    return identity


def _runtime_check() -> None:
    if not sys.platform.startswith("linux"):
        raise DiscoveryError("incompatible")
    version = platform.python_version()
    if not version.startswith("3.12.") or unicodedata.unidata_version != "15.0.0":
        raise DiscoveryError("incompatible")


def _validate_tool_identity(identity: dict[str, Any], caller_digest: str) -> None:
    if validate_definition(identity, "toolIdentity") or not verify_object_digest("tool_identity", identity):
        raise DiscoveryError("incompatible", caller_request_digest=caller_digest)
    if identity["kind"] != "development_runtime":
        raise DiscoveryError("unsupported_identity", caller_request_digest=caller_digest)
    if identity["python_version"] != platform.python_version() or identity["unicode_data"] != unicodedata.unidata_version:
        raise DiscoveryError("incompatible", caller_request_digest=caller_digest)


def validate_request(request: dict[str, Any]) -> str:
    try:
        caller_digest = object_digest("caller_request", request)
    except ProtocolError as exc:
        raise DiscoveryError("invalid_request") from exc
    query = request.get("query") if type(request) is dict else None
    limits = request.get("limits") if type(request) is dict else None
    query_bytes = limits.get("query_bytes") if type(limits) is dict else None
    if type(query) is str and type(query_bytes) is int and len(query.encode("utf-8")) > query_bytes:
        raise DiscoveryError("resource_exhausted", caller_request_digest=caller_digest)
    if validate_definition(request, "request"):
        raise DiscoveryError("invalid_request", caller_request_digest=caller_digest)
    request_failures = validate_invariants(request, "request")
    if "query UTF-8 byte limit" in request_failures:
        raise DiscoveryError("resource_exhausted", caller_request_digest=caller_digest)
    if request_failures:
        raise DiscoveryError("invalid_request", caller_request_digest=caller_digest)
    if request["algorithm"] != ALGORITHM["id"]:
        raise DiscoveryError("invalid_request", caller_request_digest=caller_digest)
    return caller_digest


def _normalized_values(document: DiscoveryDocument) -> dict[str, tuple[str, ...]]:
    values = {
        "id": (document.ont_id,),
        "label": document.labels,
        "synonym": document.synonyms,
        "description": (document.description,),
        "relation": document.relations,
        "example": document.examples,
        "anti_example": document.anti_examples,
    }
    return {family: tuple(normalize_lexical(value) for value in family_values) for family, family_values in values.items()}


def _score_document(document: DiscoveryDocument, query: str, query_tokens: list[str]) -> dict[str, Any] | None:
    values = _normalized_values(document)
    token_sets = {family: tuple(set(lexical_tokens(value)) for value in family_values) for family, family_values in values.items()}
    score = 0
    matched: set[str] = set()
    evidence: list[dict[str, str]] = []

    for family in ("id", "label", "synonym", "description", "relation", "example"):
        token_weight, phrase_weight = _POSITIVE_WEIGHTS[family]
        family_values = values[family]
        family_tokens = token_sets[family]
        if query in family_values:
            score += phrase_weight
            evidence.append({"field": family, "rule": "phrase_exact", "query_term": query})
        for token in query_tokens:
            if any(token in tokens for tokens in family_tokens):
                score += token_weight
                matched.add(token)
                evidence.append({"field": family, "rule": "token_exact", "query_term": token})

    anti_values = values["anti_example"]
    anti_tokens = token_sets["anti_example"]
    if query in anti_values:
        score -= 400
        evidence.append({"field": "anti_example", "rule": "anti_phrase", "query_term": query})
    for token in query_tokens:
        if any(token in tokens for tokens in anti_tokens):
            score -= 200
            evidence.append({"field": "anti_example", "rule": "anti_token", "query_term": token})

    score = min(4_294_967_295, max(0, score))
    if score < 100:
        return None
    if len(evidence) > 256:
        raise DiscoveryError("resource_exhausted")
    return {
        "rank": 0,
        "ont_id": document.ont_id,
        "kind": document.kind,
        "layer": document.layer,
        "score": score,
        "matched_query_tokens": [token for token in query_tokens if token in matched],
        "evidence": evidence,
        "document_digest": document.document_digest,
    }


def _classify(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "no_candidates"
    if all(candidate["score"] < 300 for candidate in candidates):
        return "low_confidence"
    if len(candidates) == 1:
        return "unique_candidate"
    if candidates[0]["score"] == candidates[1]["score"] and candidates[0]["matched_query_tokens"] == candidates[1]["matched_query_tokens"]:
        return "ambiguous_equivalence"
    return "multiple_candidates"


def discover(
    corpus: CapturedCorpus,
    request: dict[str, Any],
    *,
    tool_identity: dict[str, Any],
) -> DiscoveryExecution:
    caller_digest = validate_request(request)
    _runtime_check()
    _validate_tool_identity(tool_identity, caller_digest)
    selector = request["identity_selector"]
    if selector["kind"] != "development_snapshot":
        raise DiscoveryError("unsupported_identity", caller_request_digest=caller_digest)
    snapshot = corpus.snapshot
    if request["profile"] != snapshot["profile"]:
        raise DiscoveryError("invalid_request", caller_request_digest=caller_digest)

    effective: dict[str, Any] = {
        "schema": "semantic-effective-execution.v0",
        "caller_request_digest": caller_digest,
        "corpus_snapshot_digest": snapshot["corpus_snapshot_digest"],
        "tool_identity": tool_identity,
        "algorithm": dict(ALGORITHM),
        "effective_limits": dict(request["limits"]),
    }
    effective["effective_execution_digest"] = object_digest("effective_execution", effective)
    if validate_protocol(effective) or validate_invariants(effective):
        raise DiscoveryError("internal", caller_request_digest=caller_digest)

    normalized_query = normalize_lexical(request["query"])
    query_tokens = lexical_tokens(request["query"])
    if not query_tokens:
        raise DiscoveryError("invalid_request", caller_request_digest=caller_digest)
    full = [candidate for document in corpus.documents if (candidate := _score_document(document, normalized_query, query_tokens)) is not None]
    full.sort(key=lambda candidate: (-candidate["score"], candidate["ont_id"].encode(), 0 if candidate["kind"] == "concept" else 1))
    for rank, candidate in enumerate(full, 1):
        candidate["rank"] = rank
    retrieval = _classify(full)
    emitted = [dict(candidate) for candidate in full[:request["limits"]["candidates"]]]
    result: dict[str, Any] = {
        "schema": "semantic-discovery-result.v0",
        "caller_request_digest": caller_digest,
        "corpus_snapshot_digest": snapshot["corpus_snapshot_digest"],
        "tool_identity": tool_identity,
        "effective_execution_digest": effective["effective_execution_digest"],
        "algorithm": dict(ALGORITHM),
        "retrieval": retrieval,
        "candidates": emitted,
        "effective_limits": dict(request["limits"]),
        "truncated": len(full) > len(emitted),
    }
    result["result_digest"] = object_digest("result", result)
    if len(jcs_bytes(result)) > request["limits"]["result_bytes"]:
        raise DiscoveryError("resource_exhausted", caller_request_digest=caller_digest)
    failures = validate_invariants(result, request=request, eligible_candidates=full)
    if failures:
        raise DiscoveryError("internal", caller_request_digest=caller_digest)
    return DiscoveryExecution(request=request, effective_execution=effective, result=result)

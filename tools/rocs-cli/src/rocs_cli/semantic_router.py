"""Bounded deterministic interpreter for development-only semantic-router-v0."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import sys, unicodedata
from typing import Any, Mapping

from rocs_cli.discovery import DiscoveryError, discover
from rocs_cli.semantic_invariants import validate_invariants as validate_discovery_invariants
from rocs_cli.semantic_protocol import (
    ProtocolError,
    document_digest,
    jcs_bytes,
    validate_definition as validate_discovery_definition,
)
from rocs_cli.semantic_router_invariants import (
    PolicyEvaluation,
    evaluate_policy,
    validate_invariants,
)
from rocs_cli.semantic_router_protocol import (
    RouteProtocolError,
    derived_discovery_request,
    object_digest,
    shape_usage,
)
from rocs_cli.semantic_snapshot import CapturedCorpus, SnapshotError

ROUTE_ALGORITHM = {
    "id": "rocs-symbolic-router-v0",
    "candidate_algorithm": "rocs-lexical-v0",
    "unicode_data": "15.0.0",
    "normalization": "nfkc-casefold-ws-v0",
    "tokenization": "unicode-ln-sequence-v0",
}

_POLICY_RESOURCE_FAILURES = {
    "groups_per_clause limit",
    "alternatives_per_group limit",
    "concepts limit",
    "clauses limit",
    "total_alternatives limit",
    "normalized_alternative_bytes limit",
    "joint_routes limit",
}


@dataclass(frozen=True)
class RouteExecution:
    """The exact request, effective execution, and result for one route call."""

    request: dict[str, Any]
    effective_execution: dict[str, Any]
    result: dict[str, Any]

    @property
    def canonical_result_bytes(self) -> bytes:
        return jcs_bytes(self.result)


def _corpus_kinds(corpus: CapturedCorpus) -> dict[str, str]:
    """Project unique corpus identities; duplicate IDs cannot satisfy a policy."""
    kinds: dict[str, str] = {}
    try:
        for document in corpus.documents:
            ont_id, kind = document.ont_id, document.kind
            if type(ont_id) is not str or kind not in ("concept", "relation"):
                raise RouteProtocolError("invalid_ontology")
            kinds[ont_id] = kind if ont_id not in kinds else "duplicate"
    except RouteProtocolError:
        raise
    except (AttributeError, TypeError) as exc:
        raise RouteProtocolError("invalid_ontology") from exc
    return kinds


def _validate_corpus(corpus: CapturedCorpus, limits: Mapping[str, int]) -> tuple[dict[str, Any], dict[str, str]]:
    try:
        snapshot = corpus.snapshot
    except (SnapshotError, ProtocolError, AttributeError, KeyError, TypeError, ValueError) as exc:
        raise RouteProtocolError("invalid_ontology") from exc
    try:
        if validate_discovery_definition(snapshot, "corpusSnapshot") or validate_discovery_invariants(snapshot, "corpusSnapshot"):
            raise RouteProtocolError("invalid_ontology")
    except RouteProtocolError:
        raise
    except ProtocolError as exc:
        raise RouteProtocolError("incompatible") from exc
    entries = snapshot["entries"]
    if len(entries) > limits["corpus_files"] or sum(item["raw_byte_length"] for item in entries) > limits["corpus_bytes"] or any(item["raw_byte_length"] > limits["file_bytes"] for item in entries):
        raise RouteProtocolError("resource_exhausted")
    expected = sorted((item["logical_path"], item["layer"], item["layer_order"], item["kind"], item["raw_byte_length"], item["document_digest"]) for item in entries if item["kind"] in ("concept", "relation"))
    try:
        actual = sorted((item.logical_path, item.layer, item.layer_order, item.kind, len(item.raw), document_digest(item.raw)) for item in corpus.documents)
    except (AttributeError, TypeError) as exc:
        raise RouteProtocolError("invalid_ontology") from exc
    if actual != expected:
        raise RouteProtocolError("invalid_ontology")
    return snapshot, _corpus_kinds(corpus)


def _resource_shape_failures(
    policy: dict[str, Any], provenance: dict[str, Any], limits: Mapping[str, int]
) -> list[str]:
    failures: list[str] = []
    for label, value, byte_key in (
        ("policy", policy, "policy_bytes"),
        ("provenance", provenance, "provenance_bytes"),
    ):
        try:
            raw = jcs_bytes(value)
            depth, items = shape_usage(value)
        except (ProtocolError, RecursionError, TypeError, ValueError) as exc:
            raise RouteProtocolError("invalid_policy") from exc
        if len(raw) > limits[byte_key]:
            failures.append(f"{label} byte limit")
        if depth > limits["parser_depth"]:
            failures.append(f"{label} parser depth limit")
        if items > limits["collection_items"]:
            failures.append(f"{label} collection items limit")
    return failures


def _validate_inputs(
    corpus: CapturedCorpus,
    request: dict[str, Any],
    policy: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    selector = request.get("identity_selector") if type(request) is dict else None
    if type(selector) is dict and selector.get("kind") != "development_snapshot":
        raise RouteProtocolError("unsupported_identity")
    try:
        request_failures = validate_invariants(request, "routeRequest")
    except RouteProtocolError:
        raise
    except (ProtocolError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise RouteProtocolError("invalid_request") from exc
    if "query UTF-8 byte limit" in request_failures:
        raise RouteProtocolError("resource_exhausted")
    if request_failures:
        raise RouteProtocolError("invalid_request")

    limits = request["route_limits"]
    resource_failures = _resource_shape_failures(policy, provenance, limits)
    try:
        preliminary = validate_invariants(policy, "routingPolicy", provenance=provenance, route_limits=limits)
    except RouteProtocolError:
        raise
    except (ProtocolError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise RouteProtocolError("invalid_policy") from exc
    resource_failures.extend(item for item in preliminary if item in _POLICY_RESOURCE_FAILURES)
    if resource_failures:
        raise RouteProtocolError("resource_exhausted")
    _snapshot, corpus_kinds = _validate_corpus(corpus, request["discovery_limits"]) 
    try:
        policy_failures = validate_invariants(
            policy,
            "routingPolicy",
            provenance=provenance,
            route_limits=limits,
            corpus_kinds=corpus_kinds,
        )
        provenance_failures = validate_invariants(
            provenance, "provenanceManifest", policy=policy
        )
        binding_failures = validate_invariants(
            request, "routeRequest", policy=policy, provenance=provenance
        )
    except RouteProtocolError:
        raise
    except (ProtocolError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise RouteProtocolError("invalid_policy") from exc
    resource_failures.extend(
        failure for failure in policy_failures if failure in _POLICY_RESOURCE_FAILURES
    )
    if resource_failures:
        raise RouteProtocolError("resource_exhausted")
    if policy_failures or provenance_failures or binding_failures:
        raise RouteProtocolError("invalid_policy")
    return None


def _evaluate(policy: dict[str, Any], request: dict[str, Any]) -> PolicyEvaluation:
    try:
        return evaluate_policy(policy, request["query"], request["route_limits"])
    except ValueError as exc:
        # Structural policy budgets were checked already; the remaining evaluator
        # failures are the cumulative matching-work/evidence/witness budgets.
        raise RouteProtocolError("resource_exhausted") from exc
    except (ProtocolError, KeyError, TypeError, RecursionError) as exc:
        raise RouteProtocolError("invalid_policy") from exc


def _interpret(
    corpus: CapturedCorpus,
    request: dict[str, Any],
    policy: dict[str, Any],
    provenance: dict[str, Any],
    *,
    tool_identity: dict[str, Any],
) -> RouteExecution:
    if sys.version_info[:2] != (3, 12) or unicodedata.unidata_version != "15.0.0":
        raise RouteProtocolError("incompatible")
    if type(tool_identity) is not dict or tool_identity.get("kind") != "development_runtime":
        raise RouteProtocolError("unsupported_identity")
    if not str(tool_identity.get("python_version", "")).startswith("3.12.") or tool_identity.get("unicode_data") != "15.0.0":
        raise RouteProtocolError("incompatible")
    try:
        tool_failures = validate_discovery_definition(tool_identity, "toolIdentity")
    except ProtocolError as exc:
        raise RouteProtocolError("incompatible") from exc
    if tool_failures:
        raise RouteProtocolError("unsupported_identity")
    _validate_inputs(corpus, request, policy, provenance)

    # This is the sole unchanged-discovery call in the interpreter.
    discovery_execution = discover(
        corpus,
        derived_discovery_request(request),
        tool_identity=tool_identity,
    )
    evaluation = _evaluate(policy, request)
    nested_effective = discovery_execution.effective_execution
    nested_result = discovery_execution.result
    caller_digest = object_digest("caller_request", request)

    effective: dict[str, Any] = {
        "schema": "semantic-route-effective-execution.v0",
        "caller_request_digest": caller_digest,
        "corpus_snapshot_digest": nested_result["corpus_snapshot_digest"],
        "routing_policy_digest": policy["routing_policy_digest"],
        "tool_identity": deepcopy(tool_identity),
        "provenance_manifest_digest": provenance["provenance_manifest_digest"],
        "algorithm": dict(ROUTE_ALGORITHM),
        "discovery_limits": deepcopy(request["discovery_limits"]),
        "route_limits": deepcopy(request["route_limits"]),
        "nested_discovery_effective_execution_digest": nested_effective[
            "effective_execution_digest"
        ],
    }
    effective["effective_execution_digest"] = object_digest(
        "effective_execution", effective
    )
    result: dict[str, Any] = {
        "schema": "semantic-route-result.v0",
        "caller_request_digest": caller_digest,
        "corpus_snapshot_digest": effective["corpus_snapshot_digest"],
        "routing_policy_digest": effective["routing_policy_digest"],
        "tool_identity": deepcopy(tool_identity),
        "provenance_manifest_digest": effective["provenance_manifest_digest"],
        "effective_execution_digest": effective["effective_execution_digest"],
        "algorithm": dict(ROUTE_ALGORITHM),
        "admission": evaluation.admission,
        "routing": evaluation.routing,
        "evidence": evaluation.evidence,
        "discovery_result": deepcopy(nested_result),
    }
    result["result_digest"] = object_digest("result", result)
    if len(jcs_bytes(result)) > request["route_limits"]["result_bytes"]:
        raise RouteProtocolError("resource_exhausted")

    failures = validate_invariants(
        effective,
        "routeEffectiveExecution",
        request=request,
        policy=policy,
        provenance=provenance,
        discovery_effective_execution=nested_effective,
    )
    # Policy evaluation is deliberately not repeated during result validation:
    # the exact evaluation object above is the sole source of state/evidence.
    failures.extend(
        validate_invariants(
            result,
            "routeResult",
            request=request,
            provenance=provenance,
            effective_execution=effective,
        )
    )
    if failures:
        if any(
            failure.endswith(" limit")
            or failure == "policy resource accounting"
            for failure in failures
        ):
            raise RouteProtocolError("resource_exhausted")
        raise RouteProtocolError("internal")
    return RouteExecution(deepcopy(request), effective, result)


def route(
    corpus: CapturedCorpus,
    request: dict[str, Any],
    policy: dict[str, Any],
    provenance: dict[str, Any],
    *,
    tool_identity: dict[str, Any],
) -> RouteExecution:
    """Execute one bounded symbolic route over one unchanged discovery result."""
    try:
        return _interpret(
            corpus, request, policy, provenance, tool_identity=tool_identity
        )
    except RouteProtocolError as error:
        kind = error.kind
    except DiscoveryError as error:
        kind = error.kind
    except SnapshotError as error:
        kind = (
            error.kind
            if error.kind
            in ("invalid_ontology", "snapshot_changed", "resource_exhausted")
            else "internal"
        )
    except Exception:
        kind = "internal"
    # Raise outside every handler so neither cause nor context can retain unsafe
    # query, path, policy, environment, or operational exception content.
    raise RouteProtocolError(kind)

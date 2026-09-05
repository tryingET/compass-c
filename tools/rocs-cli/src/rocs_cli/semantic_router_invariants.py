"""Cross-field invariants and pure policy evaluation for semantic-router-v0."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from rocs_cli.semantic_invariants import validate_invariants as validate_discovery_invariants
from rocs_cli.semantic_protocol import object_digest as discovery_digest
from rocs_cli.semantic_router_protocol import (
    _SCHEMA_NAMES,
    alternative_tokens,
    derived_discovery_request,
    jcs_bytes,
    match_clause,
    object_digest,
    route_capabilities,
    route_tokens,
    shape_usage,
    validate_definition,
    validate_protocol,
    verify_object_digest,
)

_KIND_ORDER = {"token": 0, "phrase": 1}
_SCOPE_ORDER = {"domain": 0, "concept": 1, "joint_route": 2}
_POLARITY_ORDER = {"support": 0, "exclusion": 1}

@dataclass(frozen=True)
class PolicyEvaluation:
    admission: dict[str, Any]
    routing: dict[str, Any]
    evidence: list[dict[str, Any]]
    query_tokens: list[str]
    matching_work: int

def _bytes(value: str) -> bytes:
    return value.encode("utf-8")

def _ordered_unique(values: Iterable[Any], key: Any) -> bool:
    items = list(values)
    keys = [key(item) for item in items]
    return keys == sorted(keys) and len(keys) == len(set(keys))

def _clauses(policy: Mapping[str, Any]) -> Iterable[tuple[str, str | None, str | None, str, dict[str, Any]]]:
    for polarity, key in (("support", "admit_any"), ("exclusion", "exclude_any")):
        for clause in policy["domain"][key]:
            yield "domain", None, None, polarity, clause
    for concept in policy["concepts"]:
        for polarity, key in (("support", "support_any"), ("exclusion", "exclude_any")):
            for clause in concept[key]:
                yield "concept", concept["ont_id"], None, polarity, clause
    for route in policy["joint_routes"]:
        for polarity, key in (("support", "support_any"), ("exclusion", "exclude_any")):
            for clause in route[key]:
                yield "joint_route", None, route["joint_route_id"], polarity, clause

def _canonical_path(value: str) -> bool:
    parts = value.split("/")
    allowed = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-/")
    return (
        bool(value) and all(character in allowed for character in value)
        and not value.startswith("/") and not value.endswith("/")
        and all(part not in ("", ".", "..") for part in parts)
    )

def _policy_shape_failures(policy: dict[str, Any], limits: Mapping[str, int] | None = None) -> list[str]:
    failures: list[str] = []
    concepts = policy["concepts"]
    routes = policy["joint_routes"]
    owners = [(policy["domain"], "admit_any")] + [(item, "support_any") for item in concepts + routes]
    for owner, positive_key in owners:
        for key in (positive_key, "exclude_any"):
            if not _ordered_unique(owner[key], lambda item: _bytes(item["clause_id"])):
                failures.append("clause order or identity uniqueness")
    if not _ordered_unique(concepts, lambda item: _bytes(item["ont_id"])):
        failures.append("concept order or uniqueness")
    if not _ordered_unique(routes, lambda item: _bytes(item["joint_route_id"])):
        failures.append("joint route order or identity uniqueness")
    joint_sets: list[tuple[str, ...]] = []
    clause_ids: list[str] = []
    group_ids: list[str] = []
    total_alternatives = normalized_bytes = alternative_tokens_total = 0
    clause_count = 0
    for route in routes:
        ids = route["ont_ids"]
        if not _ordered_unique(ids, _bytes):
            failures.append("joint route ontology order or uniqueness")
        joint_sets.append(tuple(ids))
    if len(joint_sets) != len(set(joint_sets)):
        failures.append("joint route ontology set uniqueness")
    for _scope, _ont_id, _route_id, _polarity, clause in _clauses(policy):
        clause_count += 1
        clause_ids.append(clause["clause_id"])
        if not _ordered_unique(clause["all_of"], lambda item: _bytes(item["group_id"])):
            failures.append("group order or identity uniqueness")
        if limits and len(clause["all_of"]) > limits["groups_per_clause"]:
            failures.append("groups_per_clause limit")
        for group in clause["all_of"]:
            group_ids.append(group["group_id"])
            sequences: list[tuple[str, ...]] = []
            keys: list[tuple[int, bytes]] = []
            if limits and len(group["any_of"]) > limits["alternatives_per_group"]:
                failures.append("alternatives_per_group limit")
            for alternative in group["any_of"]:
                try:
                    tokens = alternative_tokens(alternative)
                except ValueError:
                    failures.append("canonical alternative")
                    continue
                sequences.append(tuple(tokens))
                keys.append((_KIND_ORDER[alternative["kind"]], _bytes(alternative["value"])))
                total_alternatives += 1
                normalized_bytes += len(alternative["value"].encode())
                alternative_tokens_total += len(tokens)
            if keys != sorted(keys):
                failures.append("alternative order")
            if len(sequences) != len(set(sequences)):
                failures.append("duplicate canonical alternative sequence")
    if len(clause_ids) != len(set(clause_ids)):
        failures.append("global clause id uniqueness")
    if len(group_ids) != len(set(group_ids)):
        failures.append("global group id uniqueness")
    if not _canonical_path(policy["authority"]["path"]):
        failures.append("canonical policy authority path")
    if limits:
        checks = {
            "concepts limit": len(concepts) <= limits["concepts"],
            "clauses limit": clause_count <= limits["clauses"],
            "total_alternatives limit": total_alternatives <= limits["total_alternatives"],
            "normalized_alternative_bytes limit": normalized_bytes <= limits["normalized_alternative_bytes"],
            "joint_routes limit": len(routes) <= limits["joint_routes"],
        }
        failures.extend(name for name, ok in checks.items() if not ok)
    policy["_s0_alternative_token_count"] = alternative_tokens_total
    return failures

def _evidence(scope: str, ont_id: str | None, route_id: str | None, polarity: str, clause: dict[str, Any], query: list[str]) -> dict[str, Any] | None:
    witnesses = match_clause(query, clause)
    if witnesses is None:
        return None
    return {
        "scope": scope, "ont_id": ont_id, "joint_route_id": route_id,
        "polarity": polarity, "clause_id": clause["clause_id"], "witnesses": witnesses,
    }

def _evaluate_collection(scope: str, ont_id: str | None, route_id: str | None, owner: dict[str, Any], query: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    positive_key = "admit_any" if scope == "domain" else "support_any"
    positive = [item for clause in owner[positive_key] if (item := _evidence(scope, ont_id, route_id, "support", clause, query))]
    negative = [item for clause in owner["exclude_any"] if (item := _evidence(scope, ont_id, route_id, "exclusion", clause, query))]
    return positive, negative

def _evidence_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _SCOPE_ORDER[item["scope"]], _bytes(item["ont_id"] or ""),
        _bytes(item["joint_route_id"] or ""), _POLARITY_ORDER[item["polarity"]],
        _bytes(item["clause_id"]),
    )

def evaluate_policy(policy: dict[str, Any], query: str, route_limits: Mapping[str, int]) -> PolicyEvaluation:
    """Evaluate the exact admission, routing, and evidence schedule."""
    query_sequence = route_tokens(query)
    scratch = deepcopy(policy)
    failures = _policy_shape_failures(scratch, route_limits)
    matching_work = len(query_sequence) * scratch.pop("_s0_alternative_token_count", 0)
    if failures or matching_work > route_limits["matching_work"]:
        raise ValueError("invalid policy shape or exhausted matching work")
    evidence: list[dict[str, Any]] = []
    domain_positive, domain_negative = _evaluate_collection("domain", None, None, policy["domain"], query_sequence)
    evidence.extend(domain_positive + domain_negative)
    d_plus = sorted((item["clause_id"] for item in domain_positive), key=_bytes)
    d_minus = sorted((item["clause_id"] for item in domain_negative), key=_bytes)
    if not d_plus and not d_minus:
        admission = ("abstained", "no_policy_domain_support")
    elif not d_plus:
        admission = ("abstained", "explicit_domain_exclusion")
    elif d_minus:
        admission = ("abstained", "domain_support_exclusion_conflict")
    else:
        admission = ("admitted", "domain_support")
    admission_value = {
        "state": admission[0], "reason": admission[1],
        "support_clause_ids": d_plus, "exclusion_clause_ids": d_minus,
    }
    supported: list[str] = []
    conflicted: list[str] = []
    route_id: str | None = None
    if admission[0] != "admitted":
        routing = ("not_evaluated", "admission_abstained", [])
    else:
        for concept in policy["concepts"]:
            positive, negative = _evaluate_collection("concept", concept["ont_id"], None, concept, query_sequence)
            evidence.extend(positive + negative)
            if positive and negative:
                conflicted.append(concept["ont_id"])
            elif positive:
                supported.append(concept["ont_id"])
        if conflicted:
            routing = ("abstained", "concept_support_exclusion_conflict", [])
        elif not supported:
            routing = ("abstained", "no_concept_support", [])
        elif len(supported) == 1:
            routing = ("single", "single_supported_concept", supported)
        else:
            exact = next((item for item in policy["joint_routes"] if item["ont_ids"] == supported), None)
            if exact is None:
                routing = ("ambiguous", "multiple_supported_without_joint_route", [])
            else:
                positive, negative = _evaluate_collection("joint_route", None, exact["joint_route_id"], exact, query_sequence)
                evidence.extend(positive + negative)
                if not positive:
                    routing = ("ambiguous", "multiple_supported_without_joint_route", [])
                elif negative:
                    routing = ("abstained", "joint_route_exclusion", [])
                else:
                    route_id = exact["joint_route_id"]
                    routing = ("multi", "explicit_joint_route", supported)
    evidence.sort(key=_evidence_key)
    witness_count = sum(len(item["witnesses"]) for item in evidence)
    if len(evidence) > route_limits["evidence_entries"] or witness_count > route_limits["witnesses"]:
        raise ValueError("evidence budget exhausted")
    routing_value = {
        "state": routing[0], "reason": routing[1], "selected_ont_ids": list(routing[2]),
        "supported_ont_ids": supported, "conflicted_ont_ids": conflicted,
        "joint_route_id": route_id,
    }
    return PolicyEvaluation(admission_value, routing_value, evidence, query_sequence, matching_work)


def _provenance_failures(policy: dict[str, Any], provenance: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    authority = policy["authority"]
    expected_identity = (
        policy["policy_id"], authority["owner_repo"], authority["revision"],
        authority["path"], authority["source_content_digest"],
    )
    actual_identity = (
        provenance["policy_id"], provenance["policy_owner_repo"], provenance["policy_revision"],
        provenance["policy_path"], provenance["policy_source_content_digest"],
    )
    if actual_identity != expected_identity:
        failures.append("provenance policy authority binding")
    expected: list[tuple[str, str, str, str]] = []
    for _scope, _ont, _route, _polarity, clause in _clauses(policy):
        for group in clause["all_of"]:
            for alternative in group["any_of"]:
                expected.append((clause["clause_id"], group["group_id"], alternative["kind"], alternative["value"]))
    key = lambda record: (
        _bytes(record["clause_id"]), _bytes(record["group_id"]),
        _KIND_ORDER[record["kind"]], _bytes(record["value"]),
    )
    records = provenance["records"]
    if records != sorted(records, key=key):
        failures.append("provenance record order")
    actual = [(item["clause_id"], item["group_id"], item["kind"], item["value"]) for item in records]
    if sorted(actual, key=lambda item: (_bytes(item[0]), _bytes(item[1]), _KIND_ORDER[item[2]], _bytes(item[3]))) != sorted(expected, key=lambda item: (_bytes(item[0]), _bytes(item[1]), _KIND_ORDER[item[2]], _bytes(item[3]))) or len(actual) != len(set(actual)):
        failures.append("provenance alternative bijection")
    for record in records:
        if record["source_owner_repo"] != authority["owner_repo"] or not _canonical_path(record["source_path"]):
            failures.append("provenance owner or source path")
    return failures


def _lineage_failures(instance: dict[str, Any], context: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    request = context.get("request")
    policy = context.get("policy")
    provenance = context.get("provenance")
    effective = context.get("effective_execution")
    if request:
        request_digest = object_digest("caller_request", request)
        if instance.get("caller_request_digest") != request_digest:
            failures.append("caller request digest binding")
    if policy and instance.get("routing_policy_digest") != policy.get("routing_policy_digest"):
        failures.append("routing policy digest binding")
    if provenance and instance.get("provenance_manifest_digest") != provenance.get("provenance_manifest_digest"):
        failures.append("provenance manifest digest binding")
    if effective:
        for key in (
            "corpus_snapshot_digest", "routing_policy_digest", "tool_identity",
            "provenance_manifest_digest", "algorithm",
        ):
            if instance.get(key) != effective.get(key):
                failures.append(f"effective execution {key} binding")
        if instance.get("effective_execution_digest") != effective.get("effective_execution_digest"):
            failures.append("effective execution digest binding")
    return failures


def _result_state_failures(instance: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    admission = instance["admission"]
    routing = instance["routing"]
    support = admission["support_clause_ids"]
    exclusion = admission["exclusion_clause_ids"]
    expected_admission = (
        ("abstained", "no_policy_domain_support") if not support and not exclusion else
        ("abstained", "explicit_domain_exclusion") if not support else
        ("abstained", "domain_support_exclusion_conflict") if exclusion else
        ("admitted", "domain_support")
    )
    if (admission["state"], admission["reason"]) != expected_admission:
        failures.append("admission internal matrix")
    for name in ("support_clause_ids", "exclusion_clause_ids"):
        values = admission[name]
        if not _ordered_unique(values, _bytes):
            failures.append(f"{name} order or uniqueness")
    allowed = {
        "not_evaluated": {"admission_abstained"}, "single": {"single_supported_concept"},
        "multi": {"explicit_joint_route"}, "ambiguous": {"multiple_supported_without_joint_route"},
        "abstained": {"no_concept_support", "concept_support_exclusion_conflict", "joint_route_exclusion"},
    }
    if routing["reason"] not in allowed[routing["state"]]:
        failures.append("routing state reason matrix")
    selected, supported, conflicted = (routing[key] for key in ("selected_ont_ids", "supported_ont_ids", "conflicted_ont_ids"))
    for name, values in (("selected", selected), ("supported", supported), ("conflicted", conflicted)):
        if not _ordered_unique(values, _bytes):
            failures.append(f"{name} ontology order or uniqueness")
    if set(supported) & set(conflicted):
        failures.append("supported conflicted disjointness")
    if admission["state"] == "abstained" and not (
        routing["state"] == "not_evaluated" and not selected and not supported
        and not conflicted and routing["joint_route_id"] is None
    ):
        failures.append("admission abstention routing suppression")
    if admission["state"] == "admitted" and routing["state"] == "not_evaluated":
        failures.append("admitted routing evaluated")
    if routing["state"] == "single" and not (len(selected) == 1 and selected == supported and not conflicted):
        failures.append("single selection cardinality")
    if routing["state"] == "multi" and not (len(selected) > 1 and selected == supported and not conflicted and routing["joint_route_id"]):
        failures.append("multi selection cardinality")
    if routing["state"] not in ("single", "multi") and selected:
        failures.append("nonselection state selected ids")
    if routing["state"] != "multi" and routing["joint_route_id"] is not None:
        failures.append("joint route id closure")
    if conflicted and routing["reason"] != "concept_support_exclusion_conflict":
        failures.append("conflicted concept routing")
    if routing["reason"] == "concept_support_exclusion_conflict" and not conflicted:
        failures.append("conflict reason cardinality")
    if routing["reason"] == "no_concept_support" and (supported or conflicted):
        failures.append("no concept support cardinality")
    if routing["state"] == "ambiguous" and (len(supported) <= 1 or conflicted):
        failures.append("ambiguous support cardinality")
    if routing["reason"] == "joint_route_exclusion" and (len(supported) <= 1 or conflicted):
        failures.append("joint exclusion support cardinality")
    if instance["evidence"] != sorted(instance["evidence"], key=_evidence_key):
        failures.append("evidence order")
    for evidence in instance["evidence"]:
        if evidence["witnesses"] != sorted(evidence["witnesses"], key=lambda item: _bytes(item["group_id"])):
            failures.append("witness order")
        if any(item["start_token"] >= item["end_token"] for item in evidence["witnesses"]):
            failures.append("witness span")
        if (evidence["scope"] == "domain" and (evidence["ont_id"] is not None or evidence["joint_route_id"] is not None)) or (evidence["scope"] == "concept" and (evidence["ont_id"] is None or evidence["joint_route_id"] is not None)) or (evidence["scope"] == "joint_route" and (evidence["ont_id"] is not None or evidence["joint_route_id"] is None)):
            failures.append("evidence scope closure")
    return failures


def validate_invariants(instance: dict[str, Any], definition: str | None = None, **context: Any) -> list[str]:
    issues = validate_definition(instance, definition) if definition else validate_protocol(instance)
    if issues:
        return [f"schema:{issue.instance_path}:{issue.keyword}" for issue in issues]
    name = definition or _SCHEMA_NAMES.get(instance.get("schema"), "")
    if not name and instance.get("ok") is False:
        name = "routeErrorEnvelope"
    failures: list[str] = []
    if name == "routeRequest":
        if len(instance["query"].encode()) > instance["discovery_limits"]["query_bytes"]:
            failures.append("query UTF-8 byte limit")
        policy = context.get("policy")
        provenance = context.get("provenance")
        if policy and instance["expected_routing_policy_digest"] != policy.get("routing_policy_digest"):
            failures.append("expected routing policy digest binding")
        if provenance and instance["expected_provenance_manifest_digest"] != provenance.get("provenance_manifest_digest"):
            failures.append("expected provenance manifest digest binding")
    elif name == "routingPolicy":
        if not verify_object_digest("routing_policy", instance):
            failures.append("routing policy digest")
        scratch = deepcopy(instance)
        failures.extend(_policy_shape_failures(scratch, context.get("route_limits")))
        provenance = context.get("provenance")
        if provenance:
            if instance["provenance_manifest_digest"] != provenance.get("provenance_manifest_digest"):
                failures.append("policy provenance manifest digest binding")
            failures.extend(_provenance_failures(instance, provenance))
        corpus_kinds = context.get("corpus_kinds")
        if corpus_kinds is not None:
            concept_ids = [item["ont_id"] for item in instance["concepts"]]
            if any(corpus_kinds.get(item) != "concept" for item in concept_ids):
                failures.append("policy concept corpus identity")
            if any(item not in concept_ids for route in instance["joint_routes"] for item in route["ont_ids"]):
                failures.append("joint route concept identity")
    elif name == "provenanceManifest":
        if not verify_object_digest("provenance_manifest", instance):
            failures.append("provenance manifest digest")
        if not _canonical_path(instance["policy_path"]):
            failures.append("canonical provenance policy path")
        policy = context.get("policy")
        if policy:
            failures.extend(_provenance_failures(policy, instance))
    elif name == "routeEffectiveExecution":
        if not verify_object_digest("effective_execution", instance):
            failures.append("effective execution digest")
        if instance["tool_identity"]["digest"] != discovery_digest("tool_identity", instance["tool_identity"]):
            failures.append("tool identity digest")
        failures.extend(_lineage_failures(instance, context))
        request = context.get("request")
        if request and (instance["discovery_limits"] != request["discovery_limits"] or instance["route_limits"] != request["route_limits"]):
            failures.append("effective limits binding")
        nested = context.get("discovery_effective_execution")
        if nested:
            nested_failures = validate_discovery_invariants(nested, "effectiveExecution")
            failures.extend(f"nested discovery effective execution:{item}" for item in nested_failures)
            if instance["nested_discovery_effective_execution_digest"] != nested.get("effective_execution_digest"):
                failures.append("nested discovery effective execution digest binding")
            if request:
                derived_digest = discovery_digest("caller_request", derived_discovery_request(request))
                expected = {
                    "caller_request_digest": derived_digest, "corpus_snapshot_digest": instance["corpus_snapshot_digest"],
                    "tool_identity": instance["tool_identity"], "algorithm": {"id": "rocs-lexical-v0", "unicode_data": "15.0.0"},
                    "effective_limits": request["discovery_limits"],
                }
                for key, value in expected.items():
                    if nested.get(key) != value:
                        failures.append(f"nested discovery effective execution {key} binding")
    elif name == "routeResult":
        if not verify_object_digest("result", instance):
            failures.append("route result digest")
        failures.extend(_result_state_failures(instance))
        failures.extend(_lineage_failures(instance, context))
        request = context.get("request")
        policy = context.get("policy")
        if request and policy:
            try:
                expected = evaluate_policy(policy, request["query"], request["route_limits"])
                if instance["admission"] != expected.admission:
                    failures.append("admission matrix or clause binding")
                if instance["routing"] != expected.routing:
                    failures.append("routing matrix or identity binding")
                if instance["evidence"] != expected.evidence:
                    failures.append("evidence schedule or witness binding")
            except ValueError:
                failures.append("policy resource accounting")
        discovery = instance["discovery_result"]
        if request:
            derived = derived_discovery_request(request)
            if discovery["caller_request_digest"] != discovery_digest("caller_request", derived):
                failures.append("nested discovery caller request binding")
            failures.extend(f"nested discovery:{item}" for item in validate_discovery_invariants(discovery, request=derived))
            if discovery["effective_limits"] != request["discovery_limits"]:
                failures.append("nested discovery limits binding")
            if len(jcs_bytes(instance)) > request["route_limits"]["result_bytes"]:
                failures.append("route result byte limit")
        if discovery["corpus_snapshot_digest"] != instance["corpus_snapshot_digest"] or discovery["tool_identity"] != instance["tool_identity"]:
            failures.append("nested discovery lineage binding")
        effective = context.get("effective_execution")
        if effective and discovery["effective_execution_digest"] != effective["nested_discovery_effective_execution_digest"]:
            failures.append("nested discovery effective execution binding")
    elif name == "routeErrorEnvelope":
        error = instance["error"]
        from rocs_cli.semantic_router_protocol import SAFE_ERROR_MESSAGES
        if error["message"] != SAFE_ERROR_MESSAGES[error["kind"]]:
            failures.append("safe error message")
    elif name == "routeCapabilities":
        if instance != route_capabilities():
            failures.append("route capabilities exactness")
    return failures


def validate_bundle(
    *, request: dict[str, Any], policy: dict[str, Any], provenance: dict[str, Any],
    effective_execution: dict[str, Any], result: dict[str, Any],
    discovery_effective_execution: dict[str, Any] | None = None,
    corpus_kinds: Mapping[str, str] | None = None,
) -> list[str]:
    context = {
        "request": request, "policy": policy, "provenance": provenance,
        "effective_execution": effective_execution,
        "discovery_effective_execution": discovery_effective_execution,
        "corpus_kinds": corpus_kinds,
    }
    failures: list[str] = []
    failures.extend(validate_invariants(request, **context))
    failures.extend(validate_invariants(policy, request=request, provenance=provenance, route_limits=request["route_limits"], corpus_kinds=corpus_kinds))
    failures.extend(validate_invariants(provenance, request=request, policy=policy))
    limits = request["route_limits"]
    for label, value, byte_limit in (
        ("policy", policy, limits["policy_bytes"]),
        ("provenance", provenance, limits["provenance_bytes"]),
    ):
        depth, items = shape_usage(value)
        if len(jcs_bytes(value)) > byte_limit:
            failures.append(f"{label} byte limit")
        if depth > limits["parser_depth"]:
            failures.append(f"{label} parser depth limit")
        if items > limits["collection_items"]:
            failures.append(f"{label} collection items limit")
    failures.extend(validate_invariants(effective_execution, **context))
    failures.extend(validate_invariants(result, **context))
    return failures

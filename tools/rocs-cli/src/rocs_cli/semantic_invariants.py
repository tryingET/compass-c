"""Cross-field invariant checks for Semantic Discovery Protocol v0."""
from __future__ import annotations

import unicodedata
from copy import deepcopy
from typing import Any, Iterable

from rocs_cli.semantic_protocol import (
    _SCHEMA_NAMES, document_digest, jcs_bytes, lexical_tokens, normalize_lexical,
    query_limit_outcome, validate_definition, validate_protocol, verify_object_digest,
)

def _sorted_unique(values: Iterable[Any], key: Any) -> bool:
    materialized = list(values)
    return materialized == sorted(materialized, key=key) and len(materialized) == len({key(value) for value in materialized})


def validate_invariants(
    instance: dict[str, Any],
    definition: str | None = None,
    *,
    request: dict[str, Any] | None = None,
    eligible_candidates: list[dict[str, Any]] | None = None,
    eligible_count: int | None = None,
) -> list[str]:
    """Check all cross-field invariants observable from one protocol envelope."""
    issues = validate_definition(instance, definition) if definition else validate_protocol(instance)
    if issues:
        return [f"schema:{issue.instance_path}:{issue.keyword}" for issue in issues]
    name = definition or _SCHEMA_NAMES.get(instance.get("schema"), "")
    if not name and instance.get("ok") is False and "error" in instance:
        name = "errorEnvelope"
    failures: list[str] = []

    def check_digest(kind: str, value: dict[str, Any]) -> None:
        if not verify_object_digest(kind, value):
            failures.append(f"{kind} digest")

    if name == "request":
        if query_limit_outcome(instance["query"], instance["limits"]["query_bytes"]) != "accept":
            failures.append("query UTF-8 byte limit")
    elif name == "corpusSnapshot":
        check_digest("corpus_snapshot", instance)
        roots = instance["roots"]
        if not _sorted_unique(roots, lambda x: (x["layer_order"], x["root_id"].encode())):
            failures.append("roots order or identity uniqueness")
        if len({x["root_id"] for x in roots}) != len(roots):
            failures.append("root id uniqueness")
        if len({x["layer_order"] for x in roots}) != len(roots) or len({x["layer"] for x in roots}) != len(roots):
            failures.append("root layer order/layer uniqueness")
        refs = instance["resolved_refs"]
        if refs != sorted(refs, key=lambda x: (x["layer_order"], x["layer"].encode(), x["locator"].encode())):
            failures.append("resolved ref order")
        expected = {(x["layer"], x["layer_order"]) for x in roots if x["kind"] == "ref"}
        actual = [(x["layer"], x["layer_order"]) for x in refs]
        if set(actual) != expected or len(actual) != len(set(actual)):
            failures.append("one ref per ref root and none otherwise")
        entries = instance["entries"]
        if entries != sorted(entries, key=lambda x: (x["layer_order"], x["logical_path"].encode(), x["kind"])):
            failures.append("snapshot entry order")
        if len({(x["layer"], x["logical_path"]) for x in entries}) != len(entries):
            failures.append("snapshot entry uniqueness")
        if any(unicodedata.normalize("NFC", x["logical_path"]) != x["logical_path"] for x in entries):
            failures.append("logical path NFC")
    elif name == "toolIdentity":
        check_digest("tool_identity", instance)
    elif name == "effectiveExecution":
        check_digest("effective_execution", instance)
        if not verify_object_digest("tool_identity", instance["tool_identity"]):
            failures.append("tool_identity digest")
    elif name == "result":
        check_digest("result", instance)
        if not verify_object_digest("tool_identity", instance["tool_identity"]):
            failures.append("tool_identity digest")
        candidates = instance["candidates"]
        if any(candidate["score"] < 100 for candidate in candidates):
            failures.append("candidate eligibility threshold")
        if [x["rank"] for x in candidates] != list(range(1, len(candidates) + 1)):
            failures.append("candidate ranks equal 1-based array position")
        order = sorted(candidates, key=lambda x: (-x["score"], x["ont_id"].encode(), 0 if x["kind"] == "concept" else 1))
        if candidates != order:
            failures.append("candidate total order")
        if len({(x["ont_id"], x["kind"]) for x in candidates}) != len(candidates):
            failures.append("candidate identity uniqueness")
        family = {value: index for index, value in enumerate(("id", "label", "synonym", "description", "relation", "example", "anti_example"))}
        rule = {value: index for index, value in enumerate(("phrase_exact", "token_exact", "anti_phrase", "anti_token"))}
        if len(candidates) > instance["effective_limits"]["candidates"]:
            failures.append("candidate limit")
        for candidate in candidates:
            evidence = candidate["evidence"]
            query_tokens = lexical_tokens(request["query"]) if request is not None else candidate["matched_query_tokens"]
            position = {token: index for index, token in enumerate(query_tokens)}
            keys = [(family[x["field"]], rule[x["rule"]], 0 if "phrase" in x["rule"] else position.get(x["query_term"], 1 << 30), x["query_term"].encode()) for x in evidence]
            if keys != sorted(keys):
                failures.append("field/rule/query order")
            positive_order = list(dict.fromkeys(x["query_term"] for x in evidence if x["rule"] == "token_exact"))
            if request is not None:
                query_order = lexical_tokens(request["query"])
                positive_set = set(positive_order)
                positive_order = [token for token in query_order if token in positive_set]
            if candidate["matched_query_tokens"] != positive_order:
                failures.append("matched query tokens exactly positive evidence")
            for item in evidence:
                term = item["query_term"]
                if normalize_lexical(term) != term:
                    failures.append("canonical evidence query term")
                if "token" in item["rule"] and lexical_tokens(term) != [term]:
                    failures.append("canonical token predicate")
                if "token" in item["rule"] and request is not None and term not in query_tokens:
                    failures.append("token evidence belongs to query")
                if "phrase" in item["rule"] and request is not None and term != normalize_lexical(request["query"]):
                    failures.append("phrase evidence equals normalized query")
        full = eligible_candidates
        count = len(full) if full is not None else eligible_count
        if instance["retrieval"] == "no_candidates":
            if candidates or count not in (None, 0):
                failures.append("no_candidates cardinality")
        elif not candidates:
            failures.append("nonempty retrieval cardinality")
        if instance["retrieval"] == "ambiguous_equivalence" and (
            (count is not None and count < 2) or (count is None and len(candidates) < 2)
        ):
            failures.append("ambiguous equivalence cardinality")
        if full is not None:
            ordered_full = sorted(full, key=lambda x: (-x["score"], x["ont_id"].encode(), 0 if x["kind"] == "concept" else 1))
            expected_length = min(instance["effective_limits"]["candidates"], len(ordered_full))
            if len(candidates) != expected_length:
                failures.append("exact top-K cardinality")
            expected_candidates = deepcopy(ordered_full[:len(candidates)])
            for rank, candidate in enumerate(expected_candidates, 1):
                candidate["rank"] = rank
            if candidates != expected_candidates:
                failures.append("exact top-K projection")
            scores = [x["score"] for x in ordered_full]
            if not scores:
                expected_retrieval = "no_candidates"
            elif all(score < 300 for score in scores):
                expected_retrieval = "low_confidence"
            elif len(ordered_full) == 1:
                expected_retrieval = "unique_candidate"
            elif ordered_full[0]["score"] == ordered_full[1]["score"] and ordered_full[0]["matched_query_tokens"] == ordered_full[1]["matched_query_tokens"]:
                expected_retrieval = "ambiguous_equivalence"
            else:
                expected_retrieval = "multiple_candidates"
            if instance["retrieval"] != expected_retrieval:
                failures.append("retrieval classification")
        if count is not None:
            if instance["truncated"] != (count > len(candidates)):
                failures.append("truncated equivalence")
            if count < len(candidates):
                failures.append("eligible candidate count")
        if len(jcs_bytes(instance)) > instance["effective_limits"]["result_bytes"]:
            failures.append("result UTF-8 byte limit")
    elif name == "packResult":
        check_digest("pack", instance)
        config = instance["config"]
        if config["rel_types"] != sorted(config["rel_types"], key=lambda x: x.encode()):
            failures.append("relation type order")
        docs = instance["documents"]
        root = docs[0]
        if root["ont_id"] != instance["root_id"] or root["document_digest"] != instance["root_document_digest"]:
            failures.append("root document first")
        if len({(x["ont_id"], x["kind"]) for x in docs}) != len(docs) or len({x["logical_path"] for x in docs}) != len(docs):
            failures.append("pack document uniqueness")
        if any(unicodedata.normalize("NFC", x["logical_path"]) != x["logical_path"] for x in docs):
            failures.append("pack logical path NFC")
        remainder = sorted(docs[1:], key=lambda x: (0 if x["kind"] == "concept" else 1, x["ont_id"].encode()))
        if docs[1:] != remainder:
            failures.append("pack document order")
        if len(docs) > config["max_docs"] or sum(len(x["text"].encode()) for x in docs) > config["max_bytes"]:
            failures.append("pack limits")
        for document in docs:
            if document_digest(document["text"].encode()) != document["document_digest"]:
                failures.append(f"document digest:{document['ont_id']}")
    elif name == "errorEnvelope":
        if len(instance["error"]["message"].encode()) > 4096:
            failures.append("error message UTF-8 byte limit")
    return failures



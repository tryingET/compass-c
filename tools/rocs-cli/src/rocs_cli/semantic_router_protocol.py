"""Strict, offline protocol substrate for semantic-router-v0."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Sequence

from rocs_cli._semantic_router_schema import SCHEMA_JSON
from rocs_cli.semantic_protocol import (
    ProtocolError,
    ValidationIssue,
    jcs_bytes,
    normalize_lexical,
    strict_json_loads,
    validate_definition as validate_discovery_definition,
)

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
DISCOVERY_RESULT_REF = (
    "https://ai-society.local/rocs/semantic-discovery-v0/protocol.schema.json#/$defs/result"
)
MAX_REQUEST_BYTES = 262_144
MAX_POLICY_BYTES = 1_048_576
MAX_PROVENANCE_BYTES = 8_388_608
MAX_DEPTH = 32
MAX_COLLECTION_ITEMS = 20_000
DOMAINS = {
    "routing_policy": ("rocs.routing-policy.v0", "routing_policy_digest"),
    "provenance_manifest": ("rocs.routing-provenance.v0", "provenance_manifest_digest"),
    "caller_request": ("rocs.route-caller-request.v0", None),
    "effective_execution": ("rocs.route-effective-execution.v0", "effective_execution_digest"),
    "result": ("rocs.route-result.v0", "result_digest"),
}
_SCHEMA_NAMES = {
    "semantic-route-request.v0": "routeRequest",
    "semantic-routing-policy.v0": "routingPolicy",
    "semantic-routing-provenance.v0": "provenanceManifest",
    "semantic-route-effective-execution.v0": "routeEffectiveExecution",
    "semantic-route-result.v0": "routeResult",
    "semantic-route-capabilities.v0": "routeCapabilities",
}
SAFE_ERROR_MESSAGES = {
    "incompatible": "runtime is incompatible with semantic-router-v0",
    "invalid_request": "route request is invalid",
    "invalid_policy": "routing policy or provenance is invalid",
    "invalid_ontology": "ontology corpus is invalid",
    "resource_exhausted": "semantic router resource limit exceeded",
    "snapshot_changed": "captured semantic router input changed",
    "unsupported_identity": "semantic router identity is unsupported",
    "internal": "semantic router internal failure",
}
_ALLOWED_SCHEMA_KEYS = {
    "$schema", "$id", "$ref", "$defs", "title", "oneOf", "type", "pattern",
    "minLength", "maxLength", "minimum", "maximum", "const", "enum", "format",
    "additionalProperties", "required", "properties", "items", "minItems", "maxItems",
}


class RouteProtocolError(ProtocolError):
    """A route protocol failure with a closed safe error mapping."""

    def __init__(self, kind: str):
        if kind not in SAFE_ERROR_MESSAGES:
            kind = "internal"
        self.kind = kind
        super().__init__(SAFE_ERROR_MESSAGES[kind])


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _issue(path: str, keyword: str, message: str, **params: Any) -> ValidationIssue:
    return ValidationIssue(path, keyword, message, params)


def load_protocol_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_JSON)
    _check_schema_bundle(schema)
    return schema


def _check_schema_bundle(schema: Any) -> None:
    if type(schema) is not dict or schema.get("$schema") != SCHEMA_DRAFT:
        raise RouteProtocolError("incompatible")

    def visit(node: Any) -> None:
        if type(node) is not dict or set(node) - _ALLOWED_SCHEMA_KEYS:
            raise RouteProtocolError("incompatible")
        ref = node.get("$ref")
        if ref is not None and not (
            type(ref) is str and (ref.startswith("#/$defs/") or ref == DISCOVERY_RESULT_REF)
        ):
            raise RouteProtocolError("incompatible")
        for key in ("$defs", "properties"):
            for child in node.get(key, {}).values():
                visit(child)
        for child in node.get("oneOf", []):
            visit(child)
        if "items" in node:
            visit(node["items"])

    visit(schema)


def _scan_limits(raw: bytes, max_depth: int, max_items: int) -> None:
    """Bound JSON container depth and members without interpreting values."""
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ProtocolError("invalid UTF-8") from exc
    stack: list[dict[str, Any]] = []
    in_string = escaped = False
    items = 0
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            if stack and stack[-1]["kind"] == "array" and stack[-1]["expect"]:
                items += 1
                stack[-1]["expect"] = False
            in_string = True
        elif character in "[{":
            if stack and stack[-1]["kind"] == "array" and stack[-1]["expect"]:
                items += 1
                stack[-1]["expect"] = False
            stack.append({"kind": "array" if character == "[" else "object", "expect": character == "["})
            if len(stack) > max_depth:
                raise RouteProtocolError("resource_exhausted")
        elif character == ":":
            if stack and stack[-1]["kind"] == "object":
                items += 1
        elif character == ",":
            if stack and stack[-1]["kind"] == "array":
                stack[-1]["expect"] = True
        elif character in "]}":
            if stack:
                stack.pop()
        elif not character.isspace() and stack and stack[-1]["kind"] == "array" and stack[-1]["expect"]:
            items += 1
            stack[-1]["expect"] = False
        if items > max_items:
            raise RouteProtocolError("resource_exhausted")


def parse_bounded_json(
    raw: bytes,
    *,
    byte_limit: int,
    malformed_kind: str,
    oversize_kind: str,
    max_depth: int = MAX_DEPTH,
    max_collection_items: int = MAX_COLLECTION_ITEMS,
) -> Any:
    if len(raw) > byte_limit:
        raise RouteProtocolError(oversize_kind)
    try:
        _scan_limits(raw, max_depth, max_collection_items)
        return strict_json_loads(raw)
    except RouteProtocolError:
        raise
    except (ProtocolError, ValueError, MemoryError, RecursionError) as exc:
        raise RouteProtocolError(malformed_kind) from exc


def shape_usage(value: Any) -> tuple[int, int]:
    """Return container depth and object-member/array-item count."""
    maximum_depth = items = 0
    stack = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if type(current) in (dict, list):
            maximum_depth = max(maximum_depth, depth)
            items += len(current)
            children = current.values() if type(current) is dict else current
            stack.extend((child, depth + 1) for child in children)
    return maximum_depth, items


def parse_request_bytes(raw: bytes) -> dict[str, Any]:
    value = parse_bounded_json(
        raw, byte_limit=MAX_REQUEST_BYTES, malformed_kind="invalid_request",
        oversize_kind="invalid_request",
    )
    if type(value) is not dict or validate_definition(value, "routeRequest"):
        raise RouteProtocolError("invalid_request")
    return value


def parse_policy_bytes(
    raw: bytes, *, byte_limit: int = MAX_POLICY_BYTES,
    parser_depth: int = MAX_DEPTH, collection_items: int = MAX_COLLECTION_ITEMS,
) -> dict[str, Any]:
    value = parse_bounded_json(
        raw, byte_limit=min(byte_limit, MAX_POLICY_BYTES), malformed_kind="invalid_policy",
        oversize_kind="resource_exhausted", max_depth=min(parser_depth, MAX_DEPTH),
        max_collection_items=min(collection_items, MAX_COLLECTION_ITEMS),
    )
    if type(value) is not dict or validate_definition(value, "routingPolicy"):
        raise RouteProtocolError("invalid_policy")
    return value


def parse_provenance_bytes(
    raw: bytes, *, byte_limit: int = MAX_PROVENANCE_BYTES,
    parser_depth: int = MAX_DEPTH, collection_items: int = MAX_COLLECTION_ITEMS,
) -> dict[str, Any]:
    value = parse_bounded_json(
        raw, byte_limit=min(byte_limit, MAX_PROVENANCE_BYTES), malformed_kind="invalid_policy",
        oversize_kind="resource_exhausted", max_depth=min(parser_depth, MAX_DEPTH),
        max_collection_items=min(collection_items, MAX_COLLECTION_ITEMS),
    )
    if type(value) is not dict or validate_definition(value, "provenanceManifest"):
        raise RouteProtocolError("invalid_policy")
    return value


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any] | None:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    if ref == DISCOVERY_RESULT_REF:
        return None
    if type(ref) is not str or not ref.startswith("#/$defs/"):
        raise RouteProtocolError("incompatible")
    resolved = root.get("$defs", {}).get(ref.removeprefix("#/$defs/"))
    if type(resolved) is not dict:
        raise RouteProtocolError("incompatible")
    return resolved


def _same(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _valid_type(value: Any, expected: str) -> bool:
    return {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(expected, False)


def _pattern_matches(pattern: str, value: str) -> bool:
    if pattern.startswith("^") and pattern.endswith("$"):
        return re.fullmatch(pattern[1:-1], value) is not None
    return re.search(pattern, value) is not None


def _valid_date_time(value: str) -> bool:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value) is None:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str) -> list[ValidationIssue]:
    resolved = _resolve(schema, root)
    if resolved is None:
        return validate_discovery_definition(value, "result")
    schema = resolved
    if "oneOf" in schema:
        branches = [_validate(value, child, root, path) for child in schema["oneOf"]]
        return [] if sum(not branch for branch in branches) == 1 else [_issue(path, "oneOf", "must match exactly one schema")]
    if "const" in schema and not _same(value, schema["const"]):
        return [_issue(path, "const", "does not equal required constant")]
    if "enum" in schema and not any(_same(value, choice) for choice in schema["enum"]):
        return [_issue(path, "enum", "is outside closed enumeration")]
    expected = schema.get("type")
    expected_types = expected if type(expected) is list else [expected] if expected else []
    if expected_types and not any(_valid_type(value, item) for item in expected_types):
        return [_issue(path, "type", "has the wrong type")]
    issues: list[ValidationIssue] = []
    if type(value) is dict:
        for key in schema.get("required", []):
            if key not in value:
                issues.append(_issue(path, "required", f"missing property: {key}", missingProperty=key))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    issues.append(_issue(path, "additionalProperties", f"forbidden property: {key}", additionalProperty=key))
        for key, child in properties.items():
            if key in value:
                issues.extend(_validate(value[key], child, root, f"{path}/{_pointer(key)}"))
    elif type(value) is list:
        if len(value) < schema.get("minItems", 0):
            issues.append(_issue(path, "minItems", "array has too few items"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            issues.append(_issue(path, "maxItems", "array has too many items"))
        for index, child in enumerate(value):
            if "items" in schema:
                issues.extend(_validate(child, schema["items"], root, f"{path}/{index}"))
    elif type(value) is str:
        if len(value) < schema.get("minLength", 0):
            issues.append(_issue(path, "minLength", "string is too short"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            issues.append(_issue(path, "maxLength", "string is too long"))
        if "pattern" in schema and not _pattern_matches(schema["pattern"], value):
            issues.append(_issue(path, "pattern", "string does not match pattern"))
        if schema.get("format") == "date-time" and not _valid_date_time(value):
            issues.append(_issue(path, "format", "string is not an RFC 3339 date-time"))
    elif type(value) is int:
        if value < schema.get("minimum", value):
            issues.append(_issue(path, "minimum", "integer is below minimum"))
        if value > schema.get("maximum", value):
            issues.append(_issue(path, "maximum", "integer is above maximum"))
    return issues


def validate_definition(instance: Any, definition: str) -> list[ValidationIssue]:
    jcs_bytes(instance)  # enforce integer-only I-JSON and scalar validity
    root = load_protocol_schema()
    selected = root["$defs"].get(definition)
    if type(selected) is not dict:
        raise RouteProtocolError("incompatible")
    return _validate(instance, selected, root, "")


def validate_protocol(instance: Any) -> list[ValidationIssue]:
    if type(instance) is not dict:
        return [_issue("", "type", "protocol instance must be an object")]
    if instance.get("ok") is False and "error" in instance:
        name = "routeErrorEnvelope"
    else:
        name = _SCHEMA_NAMES.get(instance.get("schema"), "")
    if not name:
        return [_issue("/schema", "const", "unsupported protocol schema")]
    return validate_definition(instance, name)


def require_valid(instance: Any, definition: str | None = None) -> None:
    issues = validate_definition(instance, definition) if definition else validate_protocol(instance)
    if issues:
        raise ProtocolError(f"schema {issues[0].keyword} at {issues[0].instance_path or '/'}")


def object_digest(kind: str, value: Any) -> str:
    if kind not in DOMAINS or type(value) is not dict:
        raise ProtocolError("unsupported route digest kind")
    domain, field = DOMAINS[kind]
    preimage = deepcopy(value)
    if field is not None:
        preimage.pop(field, None)
    payload = domain.encode("ascii") + b"\0" + jcs_bytes(preimage)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def verify_object_digest(kind: str, value: dict[str, Any]) -> bool:
    field = DOMAINS.get(kind, (None, None))[1]
    if field is None and kind != "caller_request":
        raise ProtocolError("unsupported route digest kind")
    return field in value and value[field] == object_digest(kind, value)


def caller_request_identity(raw: bytes) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = parse_bounded_json(
            raw, byte_limit=MAX_REQUEST_BYTES, malformed_kind="invalid_request",
            oversize_kind="invalid_request",
        )
    except RouteProtocolError:
        return None, None
    if type(value) is not dict:
        return None, None
    return value, object_digest("caller_request", value)


def derived_discovery_request(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "semantic-discovery-request.v0", "query": request["query"],
        "identity_selector": deepcopy(request["identity_selector"]), "profile": request["profile"],
        "algorithm": "rocs-lexical-v0", "limits": deepcopy(request["discovery_limits"]),
    }


def route_tokens(value: str) -> list[str]:
    normalized = normalize_lexical(value)
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        if unicodedata.category(character)[0] in ("L", "N"):
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def alternative_tokens(alternative: dict[str, Any]) -> list[str]:
    value = alternative.get("value")
    kind = alternative.get("kind")
    if type(value) is not str or kind not in ("token", "phrase"):
        raise ProtocolError("invalid alternative")
    tokens = route_tokens(value)
    canonical = " ".join(tokens)
    if value != canonical or (kind == "token" and len(tokens) != 1) or (kind == "phrase" and len(tokens) < 2):
        raise ProtocolError("non-canonical alternative")
    return tokens


def match_group(query_tokens: Sequence[str], group: dict[str, Any]) -> dict[str, Any] | None:
    matches: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for alternative in group["any_of"]:
        wanted = alternative_tokens(alternative)
        width = len(wanted)
        for start in range(len(query_tokens) - width + 1):
            if list(query_tokens[start:start + width]) == wanted:
                witness = {
                    "group_id": group["group_id"], "kind": alternative["kind"],
                    "value": alternative["value"], "start_token": start, "end_token": start + width,
                }
                key = (start, start + width, 0 if alternative["kind"] == "token" else 1, alternative["value"].encode())
                matches.append((key, witness))
    return min(matches, key=lambda item: item[0])[1] if matches else None


def match_clause(query_tokens: Sequence[str], clause: dict[str, Any]) -> list[dict[str, Any]] | None:
    witnesses = [match_group(query_tokens, group) for group in clause["all_of"]]
    if any(witness is None for witness in witnesses):
        return None
    return sorted((witness for witness in witnesses if witness is not None), key=lambda item: item["group_id"].encode())


def error_envelope(kind: str, caller_request_digest: str | None = None) -> dict[str, Any]:
    if kind not in SAFE_ERROR_MESSAGES:
        kind = "internal"
    value = {"ok": False, "error": {
        "schema": "semantic-route-error.v0", "kind": kind,
        "message": SAFE_ERROR_MESSAGES[kind], "caller_request_digest": caller_request_digest,
    }}
    require_valid(value, "routeErrorEnvelope")
    return value


def route_capabilities() -> dict[str, Any]:
    value = {
        "schema": "semantic-route-capabilities.v0",
        "request_schemas": ["semantic-route-request.v0"],
        "policy_schemas": ["semantic-routing-policy.v0"],
        "provenance_schemas": ["semantic-routing-provenance.v0"],
        "result_schemas": ["semantic-route-result.v0"],
        "error_schemas": ["semantic-route-error.v0"],
        "router_algorithms": ["rocs-symbolic-router-v0"],
        "candidate_algorithms": ["rocs-lexical-v0"],
        "unicode_data": ["15.0.0"], "normalization": ["nfkc-casefold-ws-v0"],
        "tokenization": ["unicode-ln-sequence-v0"], "platforms": ["linux"],
    }
    require_valid(value, "routeCapabilities")
    return value


def validate_invariants(instance: dict[str, Any], definition: str | None = None, **context: Any) -> list[str]:
    from rocs_cli.semantic_router_invariants import validate_invariants as check
    return check(instance, definition, **context)

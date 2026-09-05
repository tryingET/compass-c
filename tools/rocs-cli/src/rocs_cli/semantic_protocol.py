"""Deterministic semantic-discovery-v0 schema and canonicalization substrate.

This module deliberately validates the closed, packaged protocol schema rather than
providing a general-purpose JSON Schema implementation. It has no network resolver
and accepts only the Draft 2020-12 keywords used by the accepted schema bundle.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from rocs_cli._semantic_discovery_schema import SCHEMA_JSON

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SAFE_INTEGER = 9_007_199_254_740_991
DOMAINS = {
    "caller_request": "rocs.caller-request.v0",
    "corpus_snapshot": "rocs.corpus-snapshot.v0",
    "document": "rocs.document.v0",
    "tool_identity": "rocs.tool-identity.v0",
    "effective_execution": "rocs.effective-execution.v0",
    "result": "rocs.discovery-result.v0",
    "pack": "rocs.pack.v0",
}
DIGEST_FIELDS = {
    "corpus_snapshot": "corpus_snapshot_digest",
    "tool_identity": "digest",
    "effective_execution": "effective_execution_digest",
    "result": "result_digest",
    "pack": "pack_digest",
}
_SCHEMA_NAMES = {
    "semantic-discovery-request.v0": "request",
    "semantic-corpus-snapshot.v0": "corpusSnapshot",
    "semantic-effective-execution.v0": "effectiveExecution",
    "semantic-discovery-result.v0": "result",
    "semantic-pack-result.v0": "packResult",
    "semantic-discovery-capabilities.v0": "capabilities",
}
_ALLOWED_SCHEMA_KEYS = {
    "$schema", "$id", "$ref", "$defs", "title", "oneOf", "type", "pattern",
    "minLength", "maxLength", "minimum", "maximum", "const", "enum",
    "additionalProperties", "required", "properties", "items", "minItems",
    "maxItems", "uniqueItems",
}


class ProtocolError(ValueError):
    """Protocol bytes, canonicalization, schema, or invariant failure."""


@dataclass(frozen=True)
class ValidationIssue:
    instance_path: str
    keyword: str
    message: str
    params: dict[str, Any]


def load_protocol_schema() -> dict[str, Any]:
    """Return a fresh copy of the packaged schema; never resolve remote resources."""
    schema = json.loads(SCHEMA_JSON)
    _check_schema_bundle(schema)
    return schema


def _check_schema_bundle(schema: Any) -> None:
    if type(schema) is not dict or schema.get("$schema") != SCHEMA_DRAFT:
        raise ProtocolError("packaged protocol schema is not Draft 2020-12")

    def visit(node: Any) -> None:
        if type(node) is not dict:
            raise ProtocolError("packaged schema node must be an object")
        unknown = set(node) - _ALLOWED_SCHEMA_KEYS
        if unknown:
            raise ProtocolError(f"unsupported packaged schema keywords: {sorted(unknown)}")
        ref = node.get("$ref")
        if ref is not None and (type(ref) is not str or not ref.startswith("#/$defs/")):
            raise ProtocolError("packaged protocol schema contains a non-local reference")
        for child in node.get("$defs", {}).values():
            visit(child)
        for child in node.get("properties", {}).values():
            visit(child)
        for child in node.get("oneOf", []):
            visit(child)
        if "items" in node:
            visit(node["items"])

    visit(schema)


def _reject_non_ijson(value: Any, path: str = "") -> None:
    if value is None or type(value) is bool or type(value) is str:
        if type(value) is str and any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise ProtocolError(f"invalid Unicode scalar at {path or '/'}")
        return
    if type(value) is int:
        if not -SAFE_INTEGER <= value <= SAFE_INTEGER:
            raise ProtocolError(f"integer outside I-JSON interoperable range at {path or '/'}")
        return
    if type(value) is float:
        raise ProtocolError(f"floating-point numbers are forbidden at {path or '/'}")
    if type(value) is list:
        for index, child in enumerate(value):
            _reject_non_ijson(child, f"{path}/{index}")
        return
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise ProtocolError(f"non-string object key at {path or '/'}")
            _reject_non_ijson(key, path)
            _reject_non_ijson(child, f"{path}/{_pointer(key)}")
        return
    raise ProtocolError(f"non-I-JSON value at {path or '/'}")


def strict_json_loads(raw: bytes) -> Any:
    """Decode one duplicate-free, integer-only I-JSON value from UTF-8 bytes."""
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ProtocolError("input is not valid UTF-8") from exc

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ProtocolError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_float=lambda _raw: (_ for _ in ()).throw(ProtocolError("floating-point numbers are forbidden")),
            parse_int=int,
            parse_constant=lambda _raw: (_ for _ in ()).throw(ProtocolError("non-finite numbers are forbidden")),
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolError("input is not valid JSON") from exc
    _reject_non_ijson(value)
    return value


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _utf16_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def jcs_bytes(value: Any) -> bytes:
    """Return RFC 8785 bytes for the protocol's integer-only I-JSON profile."""
    _reject_non_ijson(value)

    def encode(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if type(item) is int:
            return str(item)
        if type(item) is str:
            return _quoted(item)
        if type(item) is list:
            return "[" + ",".join(encode(child) for child in item) + "]"
        keys = sorted(item, key=_utf16_key)
        return "{" + ",".join(f"{_quoted(key)}:{encode(item[key])}" for key in keys) + "}"

    return encode(value).encode("utf-8")


def domain_digest(domain: str, payload: bytes) -> str:
    if domain not in DOMAINS.values():
        raise ProtocolError(f"unknown digest domain: {domain}")
    return "sha256:" + hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def object_digest(kind: str, value: Any, *, omit_digest: bool = True) -> str:
    if kind not in DOMAINS or kind == "document":
        raise ProtocolError(f"object digest kind is not supported: {kind}")
    preimage = deepcopy(value)
    field = DIGEST_FIELDS.get(kind)
    if omit_digest and field is not None:
        if type(preimage) is not dict:
            raise ProtocolError("digest preimage must be an object")
        preimage.pop(field, None)
    return domain_digest(DOMAINS[kind], jcs_bytes(preimage))


def preimage_digest(kind: str, preimage: dict[str, Any]) -> str:
    """Hash a digest-omitted pseudotype, rejecting circular preimages."""
    field = DIGEST_FIELDS.get(kind)
    if field is None:
        raise ProtocolError(f"kind has no digest-omitted pseudotype: {kind}")
    if field in preimage:
        raise ProtocolError(f"digest key absent from preimage: {field}")
    return object_digest(kind, preimage, omit_digest=False)


def verify_object_digest(kind: str, value: dict[str, Any]) -> bool:
    field = DIGEST_FIELDS.get(kind)
    if field is None or field not in value:
        raise ProtocolError(f"complete {kind} object must contain its digest field")
    return value[field] == object_digest(kind, value)


def document_digest(raw: bytes) -> str:
    return domain_digest(DOMAINS["document"], raw)


def caller_request_identity(raw: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """Parse one caller object and return its pre-schema digest boundary."""
    try:
        value = strict_json_loads(raw)
    except ProtocolError:
        return None, None
    if type(value) is not dict:
        return None, None
    return value, object_digest("caller_request", value)


def normalize_lexical(value: str) -> str:
    if unicodedata.unidata_version != "15.0.0":
        raise ProtocolError("runtime Unicode data is not 15.0.0")
    folded = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(folded.split())


def lexical_tokens(value: str) -> list[str]:
    normalized = normalize_lexical(value)
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        if unicodedata.category(character)[0] in ("L", "N"):
            current.append(character)
        elif current:
            token = "".join(current)
            if token not in tokens:
                tokens.append(token)
            current = []
    if current:
        token = "".join(current)
        if token not in tokens:
            tokens.append(token)
    return tokens


def project_evidence(evidence: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({f"{item['field']}.{item['rule']}" for item in evidence}, key=lambda value: value.encode())


def query_limit_outcome(query: str, query_bytes: int) -> str:
    return "accept" if len(query.encode("utf-8")) <= query_bytes else "resource_exhausted"


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _same(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _unique(values: list[Any]) -> bool:
    encoded = [jcs_bytes(value) for value in values]
    return len(encoded) == len(set(encoded))


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    name = ref.removeprefix("#/$defs/")
    resolved = root.get("$defs", {}).get(name)
    if type(resolved) is not dict:
        raise ProtocolError(f"unresolved local schema reference: {ref}")
    return resolved


def _issue(path: str, keyword: str, message: str, **params: Any) -> ValidationIssue:
    return ValidationIssue(path, keyword, message, params)


def _validate(instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str) -> list[ValidationIssue]:
    schema = _resolve(schema, root)
    if "oneOf" in schema:
        branches = [_validate(instance, branch, root, path) for branch in schema["oneOf"]]
        if sum(not branch for branch in branches) != 1:
            return [_issue(path, "oneOf", "instance must match exactly one schema")]
        return []
    if "const" in schema and not _same(instance, schema["const"]):
        return [_issue(path, "const", "instance does not equal the required constant")]
    if "enum" in schema and not any(_same(instance, value) for value in schema["enum"]):
        return [_issue(path, "enum", "instance is not in the closed enumeration")]

    expected = schema.get("type")
    valid_type = {
        "object": type(instance) is dict,
        "array": type(instance) is list,
        "string": type(instance) is str,
        "integer": type(instance) is int,
        "boolean": type(instance) is bool,
        "null": instance is None,
    }.get(expected, True)
    if not valid_type:
        return [_issue(path, "type", f"instance is not of type {expected}")]

    issues: list[ValidationIssue] = []
    if type(instance) is dict:
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                issues.append(_issue(path, "required", f"required property is missing: {key}", missingProperty=key))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    issues.append(_issue(path, "additionalProperties", f"additional property is forbidden: {key}", additionalProperty=key))
        for key, subschema in properties.items():
            if key in instance:
                issues.extend(_validate(instance[key], subschema, root, f"{path}/{_pointer(key)}"))
    elif type(instance) is list:
        if len(instance) < schema.get("minItems", 0):
            issues.append(_issue(path, "minItems", "array has too few items"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(_issue(path, "maxItems", "array has too many items"))
        if schema.get("uniqueItems") and not _unique(instance):
            issues.append(_issue(path, "uniqueItems", "array items are not unique"))
        if "items" in schema:
            for index, child in enumerate(instance):
                issues.extend(_validate(child, schema["items"], root, f"{path}/{index}"))
    elif type(instance) is str:
        if len(instance) < schema.get("minLength", 0):
            issues.append(_issue(path, "minLength", "string is too short"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            issues.append(_issue(path, "maxLength", "string is too long"))
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            issues.append(_issue(path, "pattern", "string does not match the required pattern"))
    elif type(instance) is int:
        if instance < schema.get("minimum", instance):
            issues.append(_issue(path, "minimum", "integer is below the minimum"))
        if instance > schema.get("maximum", instance):
            issues.append(_issue(path, "maximum", "integer is above the maximum"))
    return issues


def validate_definition(instance: Any, definition: str) -> list[ValidationIssue]:
    _reject_non_ijson(instance)
    root = load_protocol_schema()
    selected = root["$defs"].get(definition)
    if type(selected) is not dict:
        raise ProtocolError(f"unknown protocol definition: {definition}")
    return _validate(instance, selected, root, "")


def validate_protocol(instance: Any) -> list[ValidationIssue]:
    """Validate one top-level protocol object using its closed schema discriminator."""
    if type(instance) is not dict:
        return [_issue("", "type", "protocol instance must be an object")]
    schema_name = instance.get("schema")
    if schema_name == "rocs-error.v0" or (instance.get("ok") is False and "error" in instance):
        definition = "errorEnvelope"
    else:
        definition = _SCHEMA_NAMES.get(schema_name, "")
    if not definition:
        return [_issue("/schema", "const", "unsupported protocol schema")]
    return validate_definition(instance, definition)


def require_valid(instance: Any, definition: str | None = None) -> None:
    issues = validate_definition(instance, definition) if definition else validate_protocol(instance)
    if issues:
        first = issues[0]
        raise ProtocolError(f"schema {first.keyword} at {first.instance_path or '/'}: {first.message}")


def validate_invariants(
    instance: dict[str, Any],
    definition: str | None = None,
    *,
    request: dict[str, Any] | None = None,
    eligible_candidates: list[dict[str, Any]] | None = None,
    eligible_count: int | None = None,
) -> list[str]:
    """Check all cross-field invariants observable from one protocol envelope."""
    from rocs_cli.semantic_invariants import validate_invariants as check
    return check(
        instance, definition, request=request,
        eligible_candidates=eligible_candidates, eligible_count=eligible_count,
    )


def verify_fixture_digests(golden: dict[str, Any]) -> list[str]:
    """Recompute every accepted golden digest and raw document binding."""
    valid = golden["valid"]
    expected = golden["digests"]
    computed = {
        "caller_request_digest": object_digest("caller_request", valid["request"]),
        "corpus_snapshot_digest": object_digest("corpus_snapshot", valid["corpus_snapshot"]),
        "tool_identity_digest": object_digest("tool_identity", valid["tool_identity"]),
        "effective_execution_digest": object_digest("effective_execution", valid["effective_execution"]),
        "result_digest": object_digest("result", valid["result"]),
        "pack_digest": object_digest("pack", valid["pack"]),
    }
    failures = [name for name, digest in computed.items() if expected.get(name) != digest]
    for document in valid["pack"]["documents"]:
        if document_digest(document["text"].encode()) != document["document_digest"]:
            failures.append(f"document_digest:{document['ont_id']}")
    return failures

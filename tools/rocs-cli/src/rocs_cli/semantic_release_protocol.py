"""Default-off runtime substrate for Semantic Release Protocol v0.

This module packages the accepted Decision 53 schema and deterministic
canonicalization/digest checks.  It deliberately exposes no publication,
materialization, activation, delivery, rollback, owner-store, or shell/network
operation.  Full authority-graph transition conformance remains independently
verified by the accepted Python and Node fixture validators.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Mapping

from rocs_cli.semantic_release_models import (
    DIGEST_SPECS, CheckedReleaseObject, checked_type,
)
from rocs_cli.semantic_release_schema import SCHEMA_SHA256, schema_bytes

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
PROTOCOL_ID = "https://ai-society.local/rocs/semantic-release-v0/protocol.schema.json"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 64
EXPECTED_PROTOCOL_TYPES = 54
LIVE_ACQUISITION_IMPLEMENTED = False
RUNTIME_CAPABILITIES = ("canonicalize", "schema_validate", "digest_verify")

class SemanticReleaseProtocolError(ValueError):
    """Malformed bytes, schema drift, validation failure, or digest mismatch."""


@dataclass(frozen=True)
class ValidationIssue:
    instance_path: str
    keyword: str
    message: str


@dataclass(frozen=True)
class SemanticReleaseProtocolRuntime:
    """Validation-only runtime identity; deliberately has no effect methods."""

    protocol_id: str = PROTOCOL_ID
    schema_sha256: str = SCHEMA_SHA256

    @property
    def live_acquisition_implemented(self) -> bool:
        return False

    @property
    def capabilities(self) -> tuple[str, ...]:
        return RUNTIME_CAPABILITIES

    def validate_bytes(self, raw: bytes) -> CheckedReleaseObject:
        return validate_object(strict_json_loads(raw))

    def validate_value(self, value: Mapping[str, Any]) -> CheckedReleaseObject:
        return validate_object(dict(value))


def _reject_ijson(value: Any, path: str = "") -> None:
    if value is None or type(value) is bool:
        return
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            raise SemanticReleaseProtocolError(f"non-NFC string at {path or '/'}")
        if any(
            0xD800 <= ord(character) <= 0xDFFF
            or 0xFDD0 <= ord(character) <= 0xFDEF
            or (ord(character) & 0xFFFF) in (0xFFFE, 0xFFFF)
            for character in value
        ):
            raise SemanticReleaseProtocolError(f"forbidden Unicode scalar at {path or '/'}")
        return
    if type(value) is int:
        if not 0 <= value <= MAX_SAFE_INTEGER:
            raise SemanticReleaseProtocolError(f"integer outside protocol range at {path or '/'}")
        return
    if type(value) is float:
        raise SemanticReleaseProtocolError(f"floating-point number at {path or '/'}")
    if type(value) is list:
        for index, child in enumerate(value):
            _reject_ijson(child, f"{path}/{index}")
        return
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise SemanticReleaseProtocolError(f"non-string key at {path or '/'}")
            _reject_ijson(key, path)
            _reject_ijson(child, f"{path}/{_pointer(key)}")
        return
    raise SemanticReleaseProtocolError(f"non-I-JSON value at {path or '/'}")


def _depth(value: Any) -> int:
    if type(value) is dict:
        return 1 + max((_depth(child) for child in value.values()), default=0)
    if type(value) is list:
        return 1 + max((_depth(child) for child in value), default=0)
    return 0


def strict_json_loads(raw: bytes) -> Any:
    """Read one bounded duplicate-free canonical-integer I-JSON value."""
    if type(raw) is not bytes:
        raise SemanticReleaseProtocolError("protocol input must be bytes")
    if len(raw) > MAX_INPUT_BYTES:
        raise SemanticReleaseProtocolError("protocol input exceeds byte limit")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise SemanticReleaseProtocolError("protocol input is not UTF-8") from exc

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise SemanticReleaseProtocolError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def integer(token: str) -> int:
        if re.fullmatch(r"0|[1-9][0-9]*", token) is None:
            raise SemanticReleaseProtocolError(f"non-canonical integer token: {token}")
        return int(token)

    try:
        value = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_int=integer,
            parse_float=lambda token: (_ for _ in ()).throw(
                SemanticReleaseProtocolError(f"non-integer number token: {token}")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                SemanticReleaseProtocolError(f"non-I-JSON constant: {token}")
            ),
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise SemanticReleaseProtocolError("protocol input is not valid JSON") from exc
    _reject_ijson(value)
    if _depth(value) > MAX_JSON_DEPTH:
        raise SemanticReleaseProtocolError("protocol input exceeds nesting limit")
    return value


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def jcs_bytes(value: Any) -> bytes:
    """RFC 8785 bytes for the protocol's integer-only I-JSON profile."""
    _reject_ijson(value)

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
        keys = sorted(item, key=lambda key: key.encode("utf-16-be"))
        return "{" + ",".join(f"{_quoted(key)}:{encode(item[key])}" for key in keys) + "}"

    return encode(value).encode("utf-8")


def domain_digest(domain: str, payload: bytes) -> str:
    allowed = {f"semantic-release.{suffix}.v0" for suffix, _field in DIGEST_SPECS.values()}
    allowed.update({
        "semantic-release.approval-action.v0",
        "semantic-release.authority-fact.v0",
        "semantic-release.compatibility-change.v0",
        "semantic-release.owner-acquisition-capability.v0",
        "semantic-release.owner-store-freshness-cas.v0",
        "semantic-release.raw-blob.v0",
        "semantic-release.semantic-payload.v0",
    })
    if domain not in allowed:
        raise SemanticReleaseProtocolError(f"unsupported semantic-release digest domain: {domain}")
    return "sha256:" + hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _same(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


@lru_cache(maxsize=1)
def _schema_root() -> dict[str, Any]:
    value = strict_json_loads(schema_bytes())
    if type(value) is not dict:
        raise SemanticReleaseProtocolError("embedded schema is not an object")
    if value.get("$schema") != SCHEMA_DRAFT or value.get("$id") != PROTOCOL_ID:
        raise SemanticReleaseProtocolError("embedded schema identity mismatch")
    definitions = value.get("$defs")
    branches = value.get("oneOf")
    if type(definitions) is not dict or type(branches) is not list or len(branches) != EXPECTED_PROTOCOL_TYPES:
        raise SemanticReleaseProtocolError("embedded schema inventory mismatch")
    for branch in branches:
        _resolve(branch, value)
    return value


def load_protocol_schema() -> dict[str, Any]:
    """Return a defensive copy of the embedded, integrity-checked schema."""
    return deepcopy(_schema_root())


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    if type(reference) is not str or not reference.startswith("#/$defs/"):
        raise SemanticReleaseProtocolError("schema contains a non-local reference")
    definition = root["$defs"].get(reference.removeprefix("#/$defs/"))
    if type(definition) is not dict:
        raise SemanticReleaseProtocolError(f"unresolved schema reference: {reference}")
    return definition


def _validate(instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str) -> list[ValidationIssue]:
    schema = _resolve(schema, root)
    if "oneOf" in schema:
        branches = [_validate(instance, branch, root, path) for branch in schema["oneOf"]]
        if sum(not branch for branch in branches) != 1:
            return [ValidationIssue(path, "oneOf", "instance must match exactly one branch")]
        return []
    if "const" in schema and not _same(instance, schema["const"]):
        return [ValidationIssue(path, "const", "instance differs from required constant")]
    if "enum" in schema and not any(_same(instance, choice) for choice in schema["enum"]):
        return [ValidationIssue(path, "enum", "instance is outside the closed enumeration")]

    expected = schema.get("type")
    matches = {
        "object": type(instance) is dict,
        "array": type(instance) is list,
        "string": type(instance) is str,
        "integer": type(instance) is int,
        "boolean": type(instance) is bool,
        "null": instance is None,
    }.get(expected, True)
    if not matches:
        return [ValidationIssue(path, "type", f"instance is not {expected}")]

    issues: list[ValidationIssue] = []
    if type(instance) is dict:
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                issues.append(ValidationIssue(path, "required", f"missing property: {key}"))
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    issues.append(ValidationIssue(path, "additionalProperties", f"forbidden property: {key}"))
        for key, subschema in properties.items():
            if key in instance:
                issues.extend(_validate(instance[key], subschema, root, f"{path}/{_pointer(key)}"))
    elif type(instance) is list:
        if len(instance) < schema.get("minItems", 0):
            issues.append(ValidationIssue(path, "minItems", "array has too few items"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(ValidationIssue(path, "maxItems", "array has too many items"))
        if schema.get("uniqueItems"):
            encoded = [jcs_bytes(child) for child in instance]
            if len(encoded) != len(set(encoded)):
                issues.append(ValidationIssue(path, "uniqueItems", "array items are not unique"))
        if "items" in schema:
            for index, child in enumerate(instance):
                issues.extend(_validate(child, schema["items"], root, f"{path}/{index}"))
    elif type(instance) is str:
        if len(instance) < schema.get("minLength", 0):
            issues.append(ValidationIssue(path, "minLength", "string is too short"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            issues.append(ValidationIssue(path, "maxLength", "string is too long"))
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            issues.append(ValidationIssue(path, "pattern", "string does not match pattern"))
    elif type(instance) is int:
        if instance < schema.get("minimum", instance):
            issues.append(ValidationIssue(path, "minimum", "integer is below minimum"))
        if instance > schema.get("maximum", instance):
            issues.append(ValidationIssue(path, "maximum", "integer is above maximum"))
    return issues


def _schema_const(node: dict[str, Any], root: dict[str, Any]) -> str | None:
    node = _resolve(node, root)
    direct = node.get("properties", {}).get("schema", {}).get("const")
    if type(direct) is str:
        return direct
    found = {_schema_const(branch, root) for branch in node.get("oneOf", [])}
    found.discard(None)
    if len(found) == 1:
        return found.pop()
    return None


@lru_cache(maxsize=1)
def schema_definitions() -> Mapping[str, str]:
    root = _schema_root()
    result: dict[str, str] = {}
    for branch in root["oneOf"]:
        name = branch["$ref"].removeprefix("#/$defs/")
        schema_name = _schema_const(branch, root)
        if schema_name is None or schema_name in result:
            raise SemanticReleaseProtocolError(f"ambiguous schema discriminator for {name}")
        result[schema_name] = name
    if len(result) != EXPECTED_PROTOCOL_TYPES:
        raise SemanticReleaseProtocolError("schema discriminator inventory mismatch")
    return MappingProxyType(result)


def validate_definition(instance: Any, definition: str) -> tuple[ValidationIssue, ...]:
    _reject_ijson(instance)
    root = _schema_root()
    selected = root["$defs"].get(definition)
    if type(selected) is not dict:
        raise SemanticReleaseProtocolError(f"unknown protocol definition: {definition}")
    return tuple(_validate(instance, selected, root, ""))


def validate_protocol(instance: Any) -> tuple[ValidationIssue, ...]:
    if type(instance) is not dict:
        return (ValidationIssue("", "type", "protocol instance must be an object"),)
    schema_name = instance.get("schema")
    if type(schema_name) is not str or schema_name not in schema_definitions():
        return (ValidationIssue("/schema", "const", "unsupported protocol schema"),)
    return validate_definition(instance, schema_definitions()[schema_name])


def computed_object_digest(instance: Mapping[str, Any]) -> str:
    value = dict(instance)
    schema_name = value.get("schema")
    if type(schema_name) is not str or schema_name not in DIGEST_SPECS:
        raise SemanticReleaseProtocolError("object schema has no registered digest domain")
    suffix, omitted_field = DIGEST_SPECS[schema_name]
    preimage = deepcopy(value)
    if omitted_field is not None:
        if omitted_field not in preimage:
            raise SemanticReleaseProtocolError(f"object lacks digest field: {omitted_field}")
        preimage.pop(omitted_field)
    return domain_digest(f"semantic-release.{suffix}.v0", jcs_bytes(preimage))


def _typed_digest(domain: str, value: Any) -> str:
    return domain_digest(domain, jcs_bytes(value))


def _check_derived_digests(value: dict[str, Any], path: str) -> None:
    schema_name = value.get("schema")
    if schema_name == "semantic-owner-approval.v0":
        expected = _typed_digest("semantic-release.approval-action.v0", value["action"])
        if value["action_digest"] != expected or any(
            vote["approved_action_digest"] != expected for vote in value["votes"]
        ):
            raise SemanticReleaseProtocolError(f"derived action digest mismatch at {path or '/'}")
    elif schema_name == "semantic-publication-transaction.v0":
        expected = _typed_digest("semantic-release.approval-action.v0", value["approved_action"])
        if value["approved_action_digest"] != expected:
            raise SemanticReleaseProtocolError(f"derived approved action digest mismatch at {path or '/'}")
    elif schema_name == "semantic-compatibility-override.v0":
        expected = _typed_digest("semantic-release.compatibility-change.v0", value["change"])
        if value["change_digest"] != expected:
            raise SemanticReleaseProtocolError(f"derived compatibility change digest mismatch at {path or '/'}")
    if schema_name in {
        "semantic-owner-acquisition-capability-pin.v0",
        "semantic-owner-store-read-receipt.v0",
    }:
        fact = {"fact_schema": value["fact_schema"], "fact_value": value["fact_value"]}
        if value["fact_digest"] != _typed_digest("semantic-release.authority-fact.v0", fact):
            raise SemanticReleaseProtocolError(f"derived authority fact digest mismatch at {path or '/'}")
        capability_keys = (
            "owner_repository", "acquisition_contract", "acquisition_contract_digest",
            "acquisition_distribution_digest",
        )
        capability = {key: value[key] for key in capability_keys}
        capability["owner_surface"] = (
            value["owner_surface"] if "owner_surface" in value else value["issuer"]["kind"]
        )
        if value["acquisition_capability_digest"] != _typed_digest(
            "semantic-release.owner-acquisition-capability.v0", capability
        ):
            raise SemanticReleaseProtocolError(f"derived acquisition capability digest mismatch at {path or '/'}")
    if schema_name == "semantic-owner-store-read-receipt.v0":
        token_keys = (
            "role", "category", "owner_repository", "acquisition_contract",
            "acquisition_contract_digest", "acquisition_distribution_digest", "store_id",
            "canonical_store_locator", "store_head_digest", "store_revision",
            "revocation_head_digest", "fact_schema", "fact_digest", "action_epoch",
            "required_action_epoch_floor",
        )
        token = {key: value[key] for key in token_keys}
        token["owner_surface"] = value["issuer"]["kind"]
        token["owner_id"] = value["issuer"]["id"]
        if value["freshness_cas_token_digest"] != _typed_digest(
            "semantic-release.owner-store-freshness-cas.v0", token
        ):
            raise SemanticReleaseProtocolError(f"derived freshness token digest mismatch at {path or '/'}")
    artifact = value.get("artifact")
    if type(artifact) is dict and type(artifact.get("schema")) is str and "artifact_digest" in value:
        if artifact["schema"] in DIGEST_SPECS and value["artifact_digest"] != computed_object_digest(artifact):
            raise SemanticReleaseProtocolError(f"proof artifact digest mismatch at {path or '/'}")


def _check_schema_digest_tree(value: Any, path: str = "") -> None:
    if type(value) is dict:
        schema_name = value.get("schema")
        if type(schema_name) is str and schema_name in schema_definitions():
            issues = validate_definition(value, schema_definitions()[schema_name])
            if issues:
                issue = issues[0]
                raise SemanticReleaseProtocolError(
                    f"schema {issue.keyword} at {path + issue.instance_path or '/'}: {issue.message}"
                )
            if schema_name in DIGEST_SPECS:
                computed = computed_object_digest(value)
                _suffix, omitted_field = DIGEST_SPECS[schema_name]
                if omitted_field is not None and value[omitted_field] != computed:
                    raise SemanticReleaseProtocolError(f"digest mismatch at {path or '/'}: {omitted_field}")
            _check_derived_digests(value, path)
        for key, child in value.items():
            _check_schema_digest_tree(child, f"{path}/{_pointer(key)}")
    elif type(value) is list:
        for index, child in enumerate(value):
            _check_schema_digest_tree(child, f"{path}/{index}")


def validate_object(instance: Any) -> CheckedReleaseObject:
    if type(instance) is not dict:
        raise SemanticReleaseProtocolError("protocol instance must be an object")
    # Snapshot before multi-pass checking so caller-owned containers cannot be
    # changed between schema, nested-digest, and canonicalization passes.
    snapshot = strict_json_loads(jcs_bytes(deepcopy(instance)))
    if type(snapshot) is not dict:  # pragma: no cover - established above
        raise SemanticReleaseProtocolError("protocol snapshot must be an object")
    _check_schema_digest_tree(snapshot)
    schema_name = snapshot.get("schema")
    if type(schema_name) is not str or schema_name not in schema_definitions():
        raise SemanticReleaseProtocolError("unsupported protocol schema")
    computed = computed_object_digest(snapshot)
    model_type = checked_type(schema_name)
    return model_type(
        schema=schema_name,
        definition=schema_definitions()[schema_name],
        canonical_bytes=jcs_bytes(snapshot),
        computed_digest=computed,
    )



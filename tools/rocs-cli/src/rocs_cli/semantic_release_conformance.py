"""Golden-corpus conformance helpers for Semantic Release Protocol v0."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from rocs_cli.semantic_release_models import DIGEST_SPECS
from rocs_cli.semantic_release_protocol import (
    SemanticReleaseProtocolError, domain_digest, jcs_bytes, validate_object,
)

def _pointer_value(value: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise SemanticReleaseProtocolError("chain assertion pointer is not absolute")
    current = value
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if type(current) is dict and token in current:
            current = current[token]
        elif type(current) is list and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise SemanticReleaseProtocolError(f"unresolved chain assertion pointer: {pointer}")
    return current


def verify_golden_corpus(golden: Mapping[str, Any]) -> tuple[str, ...]:
    """Verify schema, JCS preimages, and domains for the accepted golden records."""
    failures: list[str] = []
    records = golden.get("records")
    raw_preimages = golden.get("raw_preimages")
    chain_assertions = golden.get("chain_assertions")
    if type(records) is not list or type(raw_preimages) is not list or type(chain_assertions) is not list:
        return ("golden corpus shape",)
    records_by_name = {
        record.get("name"): record for record in records
        if type(record) is dict and type(record.get("name")) is str
    }
    if len(records_by_name) != len(records):
        failures.append("golden record name uniqueness")
    for record in records:
        name = record.get("name", "<unnamed>") if type(record) is dict else "<invalid>"
        try:
            if type(record) is not dict or type(record.get("instance")) is not dict:
                raise SemanticReleaseProtocolError("record shape")
            instance = record["instance"]
            validated = validate_object(instance)
            suffix, expected_field = DIGEST_SPECS[instance["schema"]]
            expected_domain = f"semantic-release.{suffix}.v0"
            if record.get("domain") != expected_domain or record.get("omitted_field") != expected_field:
                raise SemanticReleaseProtocolError("record domain or omitted field")
            preimage = deepcopy(instance)
            if expected_field is not None:
                preimage.pop(expected_field)
            if record.get("canonical_preimage") != jcs_bytes(preimage).decode("utf-8"):
                raise SemanticReleaseProtocolError("canonical preimage")
            if record.get("digest") != validated.computed_digest:
                raise SemanticReleaseProtocolError("record digest")
        except (KeyError, SemanticReleaseProtocolError) as exc:
            failures.append(f"{name}:{exc}")
    for record in raw_preimages:
        name = record.get("name", "<unnamed>") if type(record) is dict else "<invalid>"
        try:
            if type(record) is not dict or type(record.get("preimage_utf8")) is not str:
                raise SemanticReleaseProtocolError("raw preimage shape")
            computed = domain_digest(record["domain"], record["preimage_utf8"].encode("utf-8"))
            if computed != record.get("digest"):
                raise SemanticReleaseProtocolError("raw preimage digest")
        except (KeyError, SemanticReleaseProtocolError) as exc:
            failures.append(f"{name}:{exc}")
    for index, assertion in enumerate(chain_assertions):
        try:
            if type(assertion) is not dict or set(assertion) != {"record", "instance_path", "equals_record"}:
                raise SemanticReleaseProtocolError("chain assertion shape")
            subject = records_by_name[assertion["record"]]["instance"]
            expected = records_by_name[assertion["equals_record"]]["digest"]
            if _pointer_value(subject, assertion["instance_path"]) != expected:
                raise SemanticReleaseProtocolError("chain assertion mismatch")
        except (KeyError, SemanticReleaseProtocolError) as exc:
            failures.append(f"chain[{index}]:{exc}")
    return tuple(failures)

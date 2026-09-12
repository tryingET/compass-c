"""Read-only, offline custody verification; compact advisory verdicts, never model text.

Requires DSPy for exact prompt formatting and saved-output scheduler replay. No LM,
provider/auth construction, repair, grade replacement, or semantic certification.
"""

from __future__ import annotations

import argparse
import os
from importlib.metadata import version
from pathlib import Path

import compass_jury as jury
import compass_jury_budget as budget
import compass_jury_envelope as envelope
import compass_jury_live as live

ROOT, DEST, CAPTURES = live.ROOT, live.DEST, live.CAPTURES


def load(path):
    return jury.strict_json(path.read_bytes().decode("utf-8"), max_bytes=budget.RESPONSE_LIMIT)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def equal(actual, expected, message):
    require(jury.canonical(actual) == jury.canonical(expected), message)


def verify_hash(path, expected):
    digest = jury.sha(path.read_bytes())
    require(digest == expected, f"hash mismatch: {path}")
    return digest


def manifest(actual, paths, base, label):
    expected = {str(p.relative_to(base)): p for p in paths}
    require(isinstance(actual, dict) and actual and set(actual) == set(expected), label)
    for name, path in expected.items():
        verify_hash(path, actual[name])


def verify_sources(root, protocol):
    frozen = root / "inputs"
    names = ("corpus.json", "rubric.json", *(f"{c}.json" for c in CAPTURES))
    manifest(protocol.get("input_sha256"), [frozen / n for n in names], frozen, "input manifest")
    originals = sorted(live.SOURCE.glob("t*.json"))
    require(bool(originals), "missing historical sources")
    manifest(protocol.get("original_sha256"), originals, ROOT, "original manifest")
    generated = sorted(jury.PROGRAM.glob("*.py"))
    require(
        {p.name for p in generated} == {"program.py", "module.py", "signature.py", "metadata.py"},
        "generated source file set",
    )
    code = [
        *generated,
        jury.PROGRAM / "generation.json",
        *(
            ROOT / "scripts" / n
            for n in (
                "compass_jury_live.py",
                "compass_jury_budget.py",
                "compass_jury_envelope.py",
                "compass_jury.py",
            )
        ),
    ]
    manifest(protocol.get("code_sha256"), code, ROOT, "code manifest")
    manifest(
        load(jury.PROGRAM / "generation.json").get("source_sha256"),
        generated,
        jury.PROGRAM,
        "generation manifest",
    )
    for name in names:
        source = live.RUBRIC if name == "rubric.json" else live.SOURCE / name
        verify_hash(source, protocol["input_sha256"][name])
    # Prepared snapshots are NOT trusted just because the wire request agrees with them.
    return envelope.FrozenInputs(root, CAPTURES)


def verify_protocol(protocol):
    equal(version("markdown-it-py"), "4.0.0", "installed citation parser drift")
    expected = {
        "task": "AK5673",
        "captures": list(CAPTURES),
        "stages": list(jury.OUTPUTS),
        "model": "zai/glm-5.3",
        "endpoint": live.ENDPOINT,
        "temperature": 0.7,
        "max_tokens": budget.MAX_TOKENS,
        "model_context": budget.MODEL_CONTEXT,
        "max_attempts": 24,
        "attempts_basis": "stage_attempts_including_retained_response",
        "planned_new_http_attempts": 24 - len(envelope.SEED_STAGES),
        "planned_reused_responses": len(envelope.SEED_STAGES),
        "planned_cumulative_unique_review_responses": 24,
        "unique_response_basis": "completed responses only; v1 truncated response excluded",
        "citation_matching": jury.CITATION_MATCHING,
        "representation_parser": {
            "package": "markdown-it-py",
            "version": "4.0.0",
            "preset": "commonmark",
        },
        "envelope_aliases": envelope.ALIASES,
        "juror_role_lookup_aliases": jury.JUROR_ALIASES,
        "seed_root": str(envelope.SEED_ROOT.relative_to(ROOT)),
        "prior_attempt_root": str(live.PRIOR_ATTEMPT_ROOT.relative_to(ROOT)),
        "prior_response_sha256": live.PRIOR_RESPONSE_SHA256,
        "timeout_seconds": live.TIMEOUT,
        "request_limit": budget.REQUEST_LIMIT,
        "response_limit": budget.RESPONSE_LIMIT,
        "judgment_limit": budget.JUDGMENT_LIMIT,
        "cache": False,
        "retries": 0,
        "store": False,
        "store_wire_via_extra_body": True,
        "response_format": "json_object",
        "thinking_override": None,
        "billing_basis": "operator-confirmed subscription",
        "monetary_gate": False,
        "envelope_policy": {
            "outer": "one string-or-object field; canonical key or its explicit alias only",
            "finish_reason": "stop",
            "inner": "validate frozen bindings/schema/citations and prior jurors before rename",
            "repair": False,
            "original_bytes": "response.raw and output.txt remain unchanged",
            "receipt": "envelope.json records representation, keys, serialized and semantic hashes",
        },
    }
    for key, value in expected.items():
        require(key in protocol, f"missing protocol {key}")
        equal(protocol[key], value, f"protocol drift: {key}")


def verify_lineage(protocol, frozen):
    count = len(envelope.SEED_STAGES)
    sequence = [(c, f) for c in CAPTURES for f in jury.OUTPUTS]
    require(
        0 < count <= len(sequence) and list(envelope.SEED_STAGES) == sequence[:count],
        "required finite stage prefix",
    )
    require(
        all(
            len(pins) == count
            for pins in (
                envelope.SEED_RESPONSE_SHA256,
                envelope.SEED_REQUEST_SHA256,
                envelope.ORIGINAL_ROOTS,
            )
        ),
        "prefix pin count",
    )
    seed = envelope.RetainedPrefix()  # Runtime-pinned paths/hashes, not protocol-supplied pins.
    seed.verify_inputs(frozen.prepared, frozen.copies)
    equal(protocol["retained_prefix"], seed.receipts, "retained prefix lineage")
    for index, receipt in enumerate(seed.receipts):
        original = ROOT / receipt["original_response_root"] / "--".join(envelope.SEED_STAGES[index])
        verify_hash(original / "response.raw", receipt["response_sha256"])
        verify_hash(original / "request.body.json", receipt["request_sha256"])
        equal(load(original / "http.json"), {"status": 200}, "original HTTP status")
        content = load(original / "response.raw")["choices"][0]["message"]["content"]
        inner, _, reconciliation = decode_envelope(content, receipt["field"])
        equal(inner, seed.records[index]["inner"], "retained serialized judgment drift")
        equal(
            receipt,
            {
                "capture": envelope.SEED_STAGES[index][0],
                "field": envelope.SEED_STAGES[index][1],
                "source_origin": load(
                    envelope.SEED_ROOT / "--".join(envelope.SEED_STAGES[index]) / "stage.json"
                )["origin"],
                "request_sha256": envelope.SEED_REQUEST_SHA256[index],
                "response_sha256": envelope.SEED_RESPONSE_SHA256[index],
                **reconciliation,
                "original_response_root": envelope.ORIGINAL_ROOTS[index],
                "original_origin": "live_http",
            },
            "retained reconciliation receipt drift",
        )
        require(
            (original / "output.txt").read_bytes() == content.encode("utf-8"),
            "original provider output drift",
        )
    verify_hash(
        live.PRIOR_ATTEMPT_ROOT / "t059--juror_1_json/response.raw", live.PRIOR_RESPONSE_SHA256
    )
    return seed


def replay(module, inputs, outputs):
    """Execute the unchanged generated scheduler with deterministic saved-output leaves.

    This checks receipt consistency, NOT proof that the historical execution happened.
    The original signatures format the complete expected two-message wire context.
    """
    import dspy

    program = module.build_program()
    adapter = dspy.JSONAdapter(use_native_function_calling=False)
    messages, bounds = {}, {}

    class Leaf(dspy.Module):
        def __init__(self, signature):
            super().__init__()
            self.signature = signature

        def forward(self, **values):
            (field,) = self.signature.output_fields
            messages[field] = adapter.format(self.signature, [], values)
            empty_peers = {k: "" if k in jury.JURORS else v for k, v in values.items()}
            bounds[field] = (
                len(envelope.encoded(adapter.format(self.signature, [], empty_peers)))
                if field in jury.JURORS
                else budget.MESSAGE_LIMIT
            )
            require(
                [m["role"] for m in messages[field]] == ["system", "user"],
                "formatter history drift",
            )
            return dspy.Prediction(**{field: outputs[field]})

    equal(list(module.PROGRAM_OUTPUTS), list(jury.OUTPUTS), "declared outputs drift")
    for node in module.MODULE_ORDER:
        signature = getattr(program, node).predict.signature
        equal(
            list(signature.input_fields),
            module.MODULE_SIGNATURES[node]["inputs"],
            "signature inputs drift",
        )
        equal(
            list(signature.output_fields),
            module.MODULE_SIGNATURES[node]["outputs"],
            "signature outputs drift",
        )
        setattr(program, node, Leaf(signature))
    result = program(**inputs)
    equal(dict(result), outputs, "scheduler output drift")
    return program._last_runtime_trace, messages, bounds


def verify_request(stage, messages, ledger, bound):
    raw = (stage / "request.body.json").read_bytes()
    require(len(raw) <= budget.REQUEST_LIMIT, "request size")
    request = load(stage / "request.body.json")
    # stream may be omitted by the client, but no other missing/extra key is allowed.
    expected = live.request_body(messages)
    if "stream" not in request:
        expected.pop("stream")
    equal(request, expected, "wire policy or complete messages drift")
    size = len(envelope.encoded(messages))
    require(size <= bound, "message bound exceeded")
    ledger.record(size)
    equal(
        load(stage / "attempt.json"),
        {
            "attempt": ledger.calls,
            "message_bytes": size,
            "total_message_bytes": ledger.message_bytes,
        },
        "attempt accounting drift",
    )
    return request


def decode_envelope(content, field):
    """Independently verify the two lossless representations; never rewrite role labels."""
    outer = jury.strict_json(content, max_bytes=budget.RESPONSE_LIMIT)
    require(isinstance(outer, dict) and len(outer) == 1, "outer response shape")
    (observed,) = outer
    require(observed in (field, envelope.ALIASES[field]), "outer alias")
    value = outer[observed]
    require(isinstance(value, (str, dict)), "inner representation")
    is_string = isinstance(value, str)
    inner = value if is_string else jury.canonical(value)
    require(len(inner.encode("utf-8")) <= budget.JUDGMENT_LIMIT, "judgment size")
    decoded = jury.strict_json(inner)
    require(isinstance(decoded, dict), "judgment must be an object")
    if not is_string:
        equal(decoded, value, "object serialization changed decoded judgment")
    return (
        inner,
        decoded,
        {
            "input_representation": "json_string" if is_string else "json_object",
            "observed_key": observed,
            "expected_key": field,
            "serialized_inner_sha256": jury.sha(inner.encode("utf-8")),
            "semantic_sha256": jury.sha(jury.canonical(decoded).encode("utf-8")),
            "reconciled": observed != field or not is_string,
            "inner_string_unchanged": is_string,
            "decoded_judgment_unchanged": True,
        },
    )


def verify_response(stage, field, inputs, jurors, inner_saved, checked_saved):
    equal(load(stage / "http.json"), {"status": 200}, "HTTP failure")
    raw = load(stage / "response.raw")
    require(raw["model"] == "glm-5.3" and len(raw["choices"]) == 1, "reported model/choices")
    choice = raw["choices"][0]
    require(choice["finish_reason"] == "stop", "incomplete response")
    content = choice["message"]["content"]
    require(isinstance(content, str), "provider content type")
    require((stage / "output.txt").read_bytes() == content.encode("utf-8"), "provider output drift")
    inner, decoded, receipt = decode_envelope(content, field)
    equal(inner, inner_saved, "inner judgment was changed")
    equal(decoded, checked_saved, "decoded judgment was changed")
    equal(load(stage / "envelope.json"), receipt, "envelope reconciliation receipt drift")
    checked = jury.validate_judgment(
        inner, inputs, jurors if field == "adjudication_json" else None
    )
    equal(checked, decoded, "validator changed decoded judgment")
    equal(checked, checked_saved, "saved judgment drift")
    equal(load(stage / "validated.json"), checked, "validated companion drift")
    equal(
        load(stage / "usage.json"),
        {
            "usage": raw["usage"],
            "reported_model": raw["model"],
            "provider_identity_authenticated": False,
        },
        "usage companion drift",
    )
    counts = {
        "prompt_tokens": raw["usage"]["prompt_tokens"],
        "completion_tokens": raw["usage"]["completion_tokens"],
        "reasoning_tokens": raw["usage"]
        .get("completion_tokens_details", {})
        .get("reasoning_tokens", 0),
    }
    require(all(type(n) is int and n >= 0 for n in counts.values()), "usage counts")
    return receipt, checked, counts


def project_criteria(jurors, adjudication):
    return [
        {
            "id": row["id"],
            "jurors": [
                next(r["verdict"] for r in jurors[name]["criteria"] if r["id"] == row["id"])
                for name in jury.JURORS
            ],
            "adjudicator": row["verdict"],
            "disagreement": row["disagreement"],
        }
        for row in adjudication["criteria"]
    ]


def verify(root=DEST):
    root = Path(root)
    require(
        (root / "complete.json").is_file() and not (root / "failed.json").exists(),
        "incomplete pilot; do not project partial judgments as adjudication",
    )
    protocol, complete = load(root / "protocol.json"), load(root / "complete.json")
    verify_protocol(protocol)
    frozen = verify_sources(root, protocol)
    seed = verify_lineage(protocol, frozen)
    reused = len(envelope.SEED_STAGES)
    retained_origin = f"retained_{envelope.SEED_ROOT.name.rsplit('-', 1)[1]}_response"
    expected_stages = {f"{c}--{f}" for c in CAPTURES for f in jury.OUTPUTS}
    equal(sorted(p.name for p in root.glob("*--*")), sorted(expected_stages), "stage directories")
    require(not list(root.rglob("error.json")), "retained stage error")
    # Set before ANY DSPy import; never construct an LM or resolve auth.
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    module = live.program_module()
    ledger = budget.AttemptLedger()
    cases, receipts, bounds = [], [], {}
    usage = dict.fromkeys(("prompt_tokens", "completion_tokens", "reasoning_tokens"), 0)
    for capture in CAPTURES:
        inputs = frozen.prepared[capture]
        source = load(root / "inputs" / f"{capture}.json")
        saved = load(root / f"{capture}.outputs.json")
        equal(set_as_list(saved["raw_outputs"]), sorted(jury.OUTPUTS), "raw output fields")
        equal(set_as_list(saved["judgments"]), sorted(jury.OUTPUTS), "judgment fields")
        require(saved["requested_model"] == "openai/glm-5.3", "saved requested model")
        for key, value in {
            "provider_model_authenticated": False,
            "semantic_correctness_established": False,
            "action_permission": "not_granted",
        }.items():
            equal(saved[key], value, f"saved authority drift: {key}")
        trace, messages, bounds[capture] = replay(module, inputs, saved["raw_outputs"])
        equal(saved["trace"], trace, "generated trace/scheduler drift")
        jurors = {}
        for field in jury.OUTPUTS:
            ordinal = len(receipts)
            stage = root / f"{capture}--{field}"
            origin = retained_origin if ordinal < reused else "live_http"
            equal(
                load(stage / "stage.json"),
                {"capture": capture, "field": field, "origin": origin},
                "stage identity drift",
            )
            request = verify_request(stage, messages[field], ledger, bounds[capture][field])
            reconciliation, checked, counts = verify_response(
                stage, field, inputs, jurors, saved["raw_outputs"][field], saved["judgments"][field]
            )
            if ordinal < reused:
                receipt = seed.receipts[ordinal]
                verify_hash(stage / "response.raw", receipt["response_sha256"])
                verify_hash(stage / "request.body.json", receipt["request_sha256"])
                equal(request, seed.records[ordinal]["body"], "retained request body drift")
            if field in jury.JURORS:
                jurors[field] = checked
            for key, count in counts.items():
                usage[key] += count
            receipts.append(
                {
                    "stage": stage.name,
                    "origin": origin,
                    **reconciliation,
                    "request_sha256": jury.sha((stage / "request.body.json").read_bytes()),
                    "response_sha256": jury.sha((stage / "response.raw").read_bytes()),
                }
            )
        cases.append(
            {
                "capture": capture,
                "case": source["caseId"],
                "historical_arm": source["arm"],
                "criteria": project_criteria(jurors, saved["judgments"]["adjudication_json"]),
            }
        )
    equal(protocol["message_bounds"], bounds, "protocol message bounds")
    equal(
        complete,
        {
            "attempts": 24,
            "attempts_basis": "stage_attempts_including_retained_response",
            "stages": 24,
            "new_http_attempts": 24 - reused,
            "reused_responses": reused,
            "cumulative_unique_review_responses": 24,
            "message_bytes": ledger.message_bytes,
            "action_permission": "not_granted",
        },
        "completion accounting drift",
    )
    frozen.check()
    return {
        "schema_version": 3,
        "task": 5673,
        "status": "completed_advisory_review",
        "root": str(root.relative_to(ROOT)),
        "protocol_sha256": jury.sha((root / "protocol.json").read_bytes()),
        "reporter_sha256": jury.sha(Path(__file__).read_bytes()),
        "reporter_pinned_by_execution": False,
        "code_sha256": protocol["code_sha256"],
        "input_sha256": protocol["input_sha256"],
        "retained_prefix": seed.receipts,
        "representation_parser": protocol["representation_parser"],
        "model_requested_and_reported": "glm-5.3",
        "provider_identity_authenticated": False,
        "monetary_gate": False,
        "unique_review_http_responses": 24,
        "new_http_attempts": 24 - reused,
        "reused_completed_responses": reused,
        "prior_truncated_attempts_excluded_from_judgments": 1,
        "juror_calls": 18,
        "adjudicator_calls": 6,
        "all_raw_judgments_validated": True,
        "exact_fresh_request_contexts_verified": True,
        "saved_output_scheduler_replay_matches": True,
        "historical_execution_authenticated": False,
        "original_files_unchanged": len(protocol["original_sha256"]),
        "original_grades_replaced": False,
        "prior_failed_response_unchanged": True,
        "usage": usage,
        "cases": cases,
        "receipts": receipts,
        "semantic_correctness_established": False,
        "action_permission": "not_granted",
    }


def set_as_list(value):
    require(isinstance(value, dict), "expected mapping")
    return sorted(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(jury.canonical(result) + "\n")
    print(jury.canonical({"status": result["status"], "unique_review_http_responses": 24}))


if __name__ == "__main__":
    main()

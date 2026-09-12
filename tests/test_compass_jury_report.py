"""Provider-free readback checks; no live execution or output repair."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compass_jury_report as report  # noqa: E402


def test_readback_rejects_incomplete_root(tmp_path):
    (tmp_path / "failed.json").write_text("{}")
    with pytest.raises(ValueError, match="incomplete"):
        report.verify(tmp_path)


def test_hash_check_is_read_only_and_rejects_drift(tmp_path):
    path = tmp_path / "source.json"
    path.write_text('{"original": true}')
    before = path.read_bytes()
    digest = report.jury.sha(before)
    assert report.verify_hash(path, digest) == digest
    with pytest.raises(ValueError, match="hash mismatch"):
        report.verify_hash(path, "0" * 64)
    assert path.read_bytes() == before


def test_verdict_projection_retains_disagreement():
    jurors = {
        name: {"criteria": [{"id": "c", "verdict": verdict}]}
        for name, verdict in zip(report.jury.JURORS, ["pass", "fail", "pass"], strict=True)
    }
    adjudication = {
        "criteria": [{"id": "c", "verdict": "insufficient_evidence", "disagreement": True}]
    }
    rows = report.project_criteria(jurors, adjudication)
    assert rows == [
        {
            "id": "c",
            "jurors": ["pass", "fail", "pass"],
            "adjudicator": "insufficient_evidence",
            "disagreement": True,
        }
    ]
    assert json.loads(report.jury.canonical(rows)) == rows


import test_compass_jury_report_fixtures as fixtures  # noqa: E402

full_run = fixtures.full_run
put = fixtures.put


def rewrite(path, mutate):
    value = report.load(path)
    mutate(value)
    put(path, value)


def snapshot(base):
    return {
        str(p.relative_to(base)): report.jury.sha(p.read_bytes())
        for p in base.rglob("*")
        if p.is_file()
    }


def test_full_24_stage_readback_is_offline_compact_and_readonly(full_run):
    before = snapshot(full_run.base)
    result = report.verify(full_run.root)
    assert snapshot(full_run.base) == before
    assert result["new_http_attempts"] == 18
    assert result["reused_completed_responses"] == 6
    assert result["unique_review_http_responses"] == 24
    assert result["original_files_unchanged"] == 290
    assert len(result["code_sha256"]) == 9
    assert len(result["input_sha256"]) == 8
    assert len(result["cases"]) == 6
    assert len(result["receipts"]) == 24
    assert [r["origin"] for r in result["receipts"]] == ["retained_v5_response"] * 6 + [
        "live_http"
    ] * 18
    assert [r["source_origin"] for r in result["retained_prefix"]] == [
        "retained_v4_response",
        "retained_v4_response",
        "retained_v4_response",
        "retained_v4_response",
        "live_http",
        "live_http",
    ]
    assert result["retained_prefix"][0]["original_response_root"] == report.envelope.V2_ROOT
    assert result["usage"] == {
        "prompt_tokens": 288,
        "completion_tokens": 816,
        "reasoning_tokens": 120,
    }
    assert result["reporter_pinned_by_execution"] is False
    assert result["historical_execution_authenticated"] is False
    assert result["provider_identity_authenticated"] is False
    assert result["semantic_correctness_established"] is False
    assert result["action_permission"] == "not_granted"
    assert result["exact_fresh_request_contexts_verified"] is True
    assert result["saved_output_scheduler_replay_matches"] is True
    assert all(c["criteria"][0]["disagreement"] for c in result["cases"])
    text = report.jury.canonical(result)
    assert "PRIVATE" not in text and "rationale" not in text and "assessment" not in text
    assert result["reporter_sha256"] == report.jury.sha(Path(report.__file__).read_bytes())


@pytest.mark.parametrize("name", ["input_sha256", "original_sha256", "code_sha256"])
@pytest.mark.parametrize("kind", ["missing", "empty", "subset", "extra", "bad_hash"])
def test_manifest_exact_nonempty_required(full_run, name, kind):
    def tamper(value):
        if kind == "missing":
            del value[name]
        elif kind == "empty":
            value[name] = {}
        elif kind == "subset":
            value[name].pop(next(iter(value[name])))
        elif kind == "extra":
            value[name]["unexpected"] = "0" * 64
        else:
            value[name][next(iter(value[name]))] = "0" * 64

    rewrite(full_run.root / "protocol.json", tamper)
    before = snapshot(full_run.base)
    with pytest.raises(ValueError, match="manifest|hash mismatch"):
        report.verify(full_run.root)
    assert snapshot(full_run.base) == before


@pytest.mark.parametrize(
    "kind", ["source", "original", "code", "new_original", "missing_original", "generation_empty"]
)
def test_actual_files_bound_not_only_manifest_claims(full_run, kind):
    if kind == "new_original":
        put(report.live.SOURCE / "t999.json", {})
    elif kind == "missing_original":
        (report.live.SOURCE / "t001.json").unlink()
    elif kind == "generation_empty":
        path = report.jury.PROGRAM / "generation.json"
        rewrite(path, lambda v: v.update(source_sha256={}))
        rewrite(
            full_run.root / "protocol.json",
            lambda v: v["code_sha256"].update(
                {str(path.relative_to(full_run.base)): report.jury.sha(path.read_bytes())}
            ),
        )
    else:
        path = {
            "source": full_run.root / "inputs/rubric.json",
            "original": report.live.SOURCE / "t001.json",
            "code": full_run.base / "scripts/compass_jury_budget.py",
        }[kind]
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="manifest|hash mismatch"):
        report.verify(full_run.root)


def test_prepared_rubric_and_matching_wire_still_rejected_by_frozen_rebuild(full_run):
    path = full_run.root / "inputs/t060.inputs.json"
    old = report.load(path)["rubric_json"]
    changed = report.jury.canonical({"criteria": [], "rules": ["peer-selected rubric"]})
    rewrite(path, lambda v: v.update(rubric_json=changed))
    for field in report.jury.OUTPUTS:

        def inject(body):
            for message in body["messages"]:
                message["content"] = message["content"].replace(old, changed)

        rewrite(full_run.root / f"t060--{field}/request.body.json", inject)
    with pytest.raises(ValueError, match="frozen inputs mismatch"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    "kind", ["peer_system", "peer_user", "history", "missing_peer", "extra_message_key"]
)
def test_complete_wire_messages_not_substring_evidence(full_run, kind):
    field = "adjudication_json" if kind == "missing_peer" else "juror_1_json"
    path = full_run.root / f"t060--{field}/request.body.json"

    def tamper(body):
        if kind == "history":
            body["messages"].insert(1, {"role": "assistant", "content": "peer verdict"})
        elif kind == "extra_message_key":
            body["messages"][0]["name"] = "peer"
        elif kind == "missing_peer":
            peer = report.load(full_run.root / "t060.outputs.json")["raw_outputs"]["juror_3_json"]
            body["messages"][1]["content"] = body["messages"][1]["content"].replace(peer, "{}")
        else:
            peer = report.load(full_run.root / "t059.outputs.json")["raw_outputs"]["juror_2_json"]
            body["messages"][0 if kind == "peer_system" else 1]["content"] += peer

    rewrite(path, tamper)
    with pytest.raises(ValueError, match="complete messages drift"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("model", "glm-5.3-flash"),
        ("max_tokens", 8192),
        ("max_tokens", True),
        ("temperature", 0.8),
        ("n", 2),
        ("n", True),
        ("store", True),
        ("store", 0),
        ("stream", True),
        ("stream", 0),
        ("response_format", {"type": "json_schema"}),
        ("tools", []),
        ("thinking", {"type": "enabled"}),
    ],
)
def test_wire_policy_exact(full_run, key, value):
    rewrite(
        full_run.root / "t060--juror_1_json/request.body.json", lambda v: v.update({key: value})
    )
    with pytest.raises(ValueError, match="wire policy"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    "key", ["model", "max_tokens", "temperature", "n", "store", "response_format"]
)
def test_required_wire_keys_cannot_be_omitted(full_run, key):
    rewrite(full_run.root / "t060--juror_1_json/request.body.json", lambda v: v.pop(key))
    with pytest.raises(ValueError, match="wire policy"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    "kind",
    [
        "module_id",
        "primitive",
        "inputs",
        "outputs",
        "status",
        "tool_call_results",
        "scheduler_stalled",
        "missing_outputs",
        "pending",
        "final_outputs",
        "extra_call",
    ],
)
def test_generated_trace_all_fields_and_scheduler_checked(full_run, kind):
    def tamper(saved):
        trace = saved["trace"]
        if kind == "scheduler_stalled":
            trace["scheduler_events"][0]["status"] = "scheduler_stalled"
        elif kind in ("pending", "missing_outputs"):
            trace["scheduler_events"][0][kind] = ["juror_3"]
        elif kind == "final_outputs":
            trace["final_outputs"]["juror_1_json"] = "forged"
        elif kind == "extra_call":
            trace["module_calls"].append(trace["module_calls"][0])
        else:
            trace["module_calls"][0][kind] = "forged"

    rewrite(full_run.root / "t060.outputs.json", tamper)
    with pytest.raises(ValueError, match="generated trace/scheduler drift"):
        report.verify(full_run.root)


@pytest.mark.parametrize("name", ["output.txt", "validated.json", "usage.json"])
@pytest.mark.parametrize("kind", ["missing", "changed"])
def test_companion_files_required_and_verified(full_run, name, kind):
    path = full_run.root / "t060--juror_1_json" / name
    if kind == "missing":
        path.unlink()
    elif name == "output.txt":
        path.write_bytes(path.read_bytes() + b"\n")
    else:
        put(path, {})
    before = snapshot(full_run.base)
    with pytest.raises((ValueError, FileNotFoundError)):
        report.verify(full_run.root)
    assert snapshot(full_run.base) == before


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("serialized_inner_sha256", "0" * 64),
        ("semantic_sha256", "0" * 64),
        ("input_representation", "json_object"),
        ("decoded_judgment_unchanged", False),
        ("reconciled", False),
        ("reconciled", 1),
        ("inner_string_unchanged", False),
        ("observed_key", "juror_1_json"),
    ],
)
def test_lossless_alias_receipt_exact(full_run, key, value):
    # Stage 5 uses the explicit noncanonical alias.
    rewrite(full_run.root / "t060--juror_1_json/envelope.json", lambda v: v.update({key: value}))
    with pytest.raises(ValueError, match="envelope reconciliation"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    "kind",
    [
        "seed_response",
        "seed_request",
        "seed_source",
        "seed_prepared",
        "v2_response",
        "v2_request",
        "v2_output",
        "lineage",
        "origin",
        "prior_response",
        "current_seed_response",
        "current_seed_request",
    ],
)
def test_retained_lineage_and_original_bytes(full_run, kind):
    first = "t059--juror_1_json"
    if kind == "lineage":
        rewrite(
            full_run.root / "protocol.json",
            lambda v: v["retained_prefix"][0].update(original_response_root="invented"),
        )
    elif kind == "origin":
        rewrite(
            full_run.root / first / "stage.json", lambda v: v.update(origin="retained_v2_response")
        )
    else:
        paths = {
            "seed_response": full_run.seed / first / "response.raw",
            "seed_request": full_run.seed / first / "request.body.json",
            "seed_source": full_run.seed / "inputs/rubric.json",
            "seed_prepared": full_run.seed / "inputs/t059.inputs.json",
            "v2_response": full_run.base / report.envelope.V2_ROOT / first / "response.raw",
            "v2_request": full_run.base / report.envelope.V2_ROOT / first / "request.body.json",
            "v2_output": full_run.base / report.envelope.V2_ROOT / first / "output.txt",
            "prior_response": report.live.PRIOR_ATTEMPT_ROOT / first / "response.raw",
            "current_seed_response": full_run.root / first / "response.raw",
            "current_seed_request": full_run.root / first / "request.body.json",
        }
        if kind == "seed_prepared":
            rewrite(paths[kind], lambda v: v.update(rubric_json="{}"))
        else:
            paths[kind].write_bytes(paths[kind].read_bytes() + b"\n")
    with pytest.raises(ValueError):
        report.verify(full_run.root)


def replace_adjudication(run, mutate):
    """Make all saved projections agree on an invalid final-stage judgment."""
    field = "adjudication_json"
    path = run.root / "t090.outputs.json"
    saved = report.load(path)
    checked = json.loads(saved["raw_outputs"][field])
    mutate(checked)
    inner = report.jury.canonical(checked)
    saved["raw_outputs"][field] = inner
    saved["judgments"][field] = checked
    saved["trace"]["module_calls"][3]["outputs"][field] = inner
    saved["trace"]["final_outputs"][field] = inner
    put(path, saved)
    stage = run.root / f"t090--{field}"
    raw = report.load(stage / "response.raw")
    key = report.envelope.ALIASES[field]
    content = json.dumps({key: checked}, ensure_ascii=False)
    raw["choices"][0]["message"]["content"] = content
    put(stage / "response.raw", raw)
    (stage / "output.txt").write_bytes(content.encode("utf-8"))
    put(stage / "validated.json", checked)
    put(stage / "envelope.json", fixtures.receipt(key, field, inner, object_value=True))


@pytest.mark.parametrize(
    "kind", ["disagreement", "addressed_verdict", "missing_juror", "unsupported_citation"]
)
def test_independent_validation_rejects_consistently_forged_adjudication(full_run, kind):
    def tamper(checked):
        row = checked["criteria"][0]
        if kind == "disagreement":
            row["disagreement"] = False
        elif kind == "addressed_verdict":
            row["addressed_jurors"][0]["verdict"] = "fail"
        elif kind == "missing_juror":
            row["addressed_jurors"].pop()
        else:
            row["citations"] = [{"source": "tools", "quote": "invented"}]

    replace_adjudication(full_run, tamper)
    with pytest.raises(ValueError, match="disagreement|juror|citation"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("new_http_attempts", 23),
        ("reused_responses", 1),
        ("attempts", 23),
        ("stages", 23),
        ("cumulative_unique_review_responses", 25),
        ("message_bytes", 0),
    ],
)
def test_v6_completion_accounting_exact(full_run, key, value):
    rewrite(full_run.root / "complete.json", lambda v: v.update({key: value}))
    with pytest.raises(ValueError, match="completion accounting"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    "kind", ["attempt", "alias_policy", "unknown_alias", "failed", "error", "extra_stage"]
)
def test_other_fail_closed_boundaries(full_run, kind):
    if kind == "attempt":
        rewrite(full_run.root / "t060--juror_1_json/attempt.json", lambda v: v.update(attempt=1))
    elif kind == "alias_policy":
        rewrite(full_run.root / "protocol.json", lambda v: v.update(envelope_aliases={}))
    elif kind == "unknown_alias":
        stage = full_run.root / "t060--juror_1_json"
        raw = report.load(stage / "response.raw")
        content = raw["choices"][0]["message"]["content"]
        inner = next(iter(json.loads(content).values()))
        content = json.dumps({"unexpected": inner})
        raw["choices"][0]["message"]["content"] = content
        put(stage / "response.raw", raw)
        (stage / "output.txt").write_bytes(content.encode("utf-8"))
    elif kind == "failed":
        put(full_run.root / "failed.json", {})
    elif kind == "error":
        put(full_run.root / "t060--juror_1_json/error.json", {})
    else:
        (full_run.root / "unexpected--stage").mkdir()
    with pytest.raises(ValueError):
        report.verify(full_run.root)


def test_cli_explicit_new_output_only_and_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["report"])
    with pytest.raises(SystemExit):
        report.main()
    target = tmp_path / "report.json"
    result = {"status": "offline_test_only"}
    monkeypatch.setattr(report, "verify", lambda: result)
    monkeypatch.setattr(sys, "argv", ["report", "--output", str(target)])
    report.main()
    before = target.read_bytes()
    assert json.loads(before) == result
    with pytest.raises(FileExistsError):
        report.main()
    assert target.read_bytes() == before


def test_v6_object_alias_prefix_preserves_every_decoded_field(full_run):
    before = snapshot(full_run.base)
    result = report.verify(full_run.root)
    prefix = result["retained_prefix"]
    assert len(prefix) == 6
    assert [r["original_response_root"] for r in prefix] == list(report.envelope.ORIGINAL_ROOTS)
    assert all(r["original_origin"] == "live_http" for r in prefix)
    assert prefix[3]["source_origin"] == "retained_v4_response"
    field = "adjudication_json"
    stage = full_run.root / f"t059--{field}"
    content = report.load(stage / "response.raw")["choices"][0]["message"]["content"]
    decoded = json.loads(content)["adjudication_"]
    assert isinstance(decoded, dict)
    assert [r["juror"] for r in decoded["criteria"][0]["addressed_jurors"]] == [
        "juror_1_",
        "juror_2_",
        "juror_3_",
    ]
    saved = report.load(full_run.root / "t059.outputs.json")
    assert report.jury.canonical(decoded) == saved["raw_outputs"][field]
    assert decoded == saved["judgments"][field] == report.load(stage / "validated.json")
    receipt = report.load(stage / "envelope.json")
    assert receipt["input_representation"] == "json_object"
    assert receipt["inner_string_unchanged"] is False
    assert receipt["decoded_judgment_unchanged"] is True
    assert receipt["reconciled"] is True
    assert receipt["serialized_inner_sha256"] == receipt["semantic_sha256"]
    assert result["receipts"][3]["semantic_sha256"] == receipt["semantic_sha256"]
    assert prefix[0]["input_representation"] == "json_string"
    assert prefix[0]["inner_string_unchanged"] is True
    # Noncanonical string serialization must remain byte exact, not be reserialized.
    assert prefix[0]["serialized_inner_sha256"] != prefix[0]["semantic_sha256"]
    assert snapshot(full_run.base) == before


@pytest.mark.parametrize("object_value", [False, True])
@pytest.mark.parametrize("outer_alias", [False, True])
def test_adjudication_both_representations_and_keys(full_run, object_value, outer_alias):
    field = "adjudication_json"
    stage = full_run.root / f"t090--{field}"
    saved = report.load(full_run.root / "t090.outputs.json")
    inner = saved["raw_outputs"][field]
    key = report.envelope.ALIASES[field] if outer_alias else field
    raw = report.load(stage / "response.raw")
    content = json.dumps({key: json.loads(inner) if object_value else inner}, ensure_ascii=False)
    raw["choices"][0]["message"]["content"] = content
    put(stage / "response.raw", raw)
    (stage / "output.txt").write_bytes(content.encode("utf-8"))
    put(stage / "envelope.json", fixtures.receipt(key, field, inner, object_value))
    before = snapshot(full_run.base)
    result = report.verify(full_run.root)
    assert result["receipts"][-1]["reconciled"] is (outer_alias or object_value)
    assert result["receipts"][-1]["inner_string_unchanged"] is not object_value
    assert snapshot(full_run.base) == before


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("input_representation", "json_string"),
        ("observed_key", "adjudication_json"),
        ("expected_key", "adjudication_"),
        ("serialized_inner_sha256", "0" * 64),
        ("semantic_sha256", "0" * 64),
        ("reconciled", False),
        ("inner_string_unchanged", True),
        ("decoded_judgment_unchanged", False),
        ("decoded_judgment_unchanged", 1),
    ],
)
def test_each_object_reconciliation_field_independently_checked(full_run, key, value):
    rewrite(
        full_run.root / "t090--adjudication_json/envelope.json", lambda v: v.update({key: value})
    )
    with pytest.raises(ValueError, match="envelope reconciliation"):
        report.verify(full_run.root)


@pytest.mark.parametrize("target", ["provider_object", "saved_judgment", "validated_companion"])
@pytest.mark.parametrize("change", ["rationale", "role_label"])
def test_decoded_values_cannot_change_even_to_valid_alias_equivalent(full_run, target, change):
    field = "adjudication_json"
    stage = full_run.root / f"t090--{field}"

    def mutate(decoded):
        if change == "rationale":
            decoded["criteria"][0]["rationale"] += " changed"
        else:
            # Canonical role is accepted for lookup but is NOT equal to the stored alias.
            decoded["criteria"][0]["addressed_jurors"][0]["juror"] = "juror_1_json"

    if target == "provider_object":
        raw = report.load(stage / "response.raw")
        outer = json.loads(raw["choices"][0]["message"]["content"])
        mutate(outer["adjudication_"])
        content = json.dumps(outer, ensure_ascii=False)
        raw["choices"][0]["message"]["content"] = content
        put(stage / "response.raw", raw)
        (stage / "output.txt").write_bytes(content.encode("utf-8"))
        put(
            stage / "envelope.json",
            fixtures.receipt(
                "adjudication_", field, report.jury.canonical(outer["adjudication_"]), True
            ),
        )
    elif target == "saved_judgment":
        rewrite(full_run.root / "t090.outputs.json", lambda v: mutate(v["judgments"][field]))
    else:
        rewrite(stage / "validated.json", mutate)
    before = snapshot(full_run.base)
    with pytest.raises(ValueError, match="inner judgment|decoded judgment|validated companion"):
        report.verify(full_run.root)
    assert snapshot(full_run.base) == before


@pytest.mark.parametrize("label", ["juror_1", "juror_4_", "Juror_1_", "juror_2_json"])
def test_alias_lookup_only_explicit_names_and_no_duplicate_identity(full_run, label):
    def mutate(value):
        first = value["criteria"][0]["addressed_jurors"][0]
        first["juror"] = label
        if label == "juror_2_json":
            first["verdict"] = "fail"  # Reach the duplicate alias identity, not verdict mismatch.

    replace_adjudication(full_run, mutate)
    with pytest.raises(ValueError, match="unknown/duplicate juror"):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    "kind",
    [
        "missing_role_policy",
        "extra_role_alias",
        "short_prefix",
        "source_origin",
        "original_origin",
        "object_receipt",
        "v3_original",
        "fourth_source",
        "fourth_current",
        "v4_counts",
    ],
)
def test_v6_prefix_and_declared_alias_policy_exact(full_run, kind):
    path = full_run.root / "protocol.json"
    if kind == "missing_role_policy":
        rewrite(path, lambda v: v.pop("juror_role_lookup_aliases"))
    elif kind == "extra_role_alias":
        rewrite(path, lambda v: v["juror_role_lookup_aliases"].update(juror_1="juror_1_json"))
    elif kind == "short_prefix":
        rewrite(path, lambda v: v["retained_prefix"].pop())
    elif kind in ("source_origin", "original_origin"):
        rewrite(path, lambda v: v["retained_prefix"][3].update({kind: "retained_v3_response"}))
    elif kind == "object_receipt":
        rewrite(path, lambda v: v["retained_prefix"][3].update(decoded_judgment_unchanged=False))
    elif kind == "v4_counts":
        rewrite(
            full_run.root / "complete.json",
            lambda v: v.update(new_http_attempts=21, reused_responses=3),
        )
    else:
        path = {
            "v3_original": full_run.base
            / report.envelope.V3_ROOT
            / "t059--juror_2_json/response.raw",
            "fourth_source": full_run.seed / "t059--adjudication_json/response.raw",
            "fourth_current": full_run.root / "t059--adjudication_json/response.raw",
        }[kind]
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError):
        report.verify(full_run.root)


def test_v6_retained_rendered_quote_and_parser_are_explicit_and_unchanged(full_run):
    before = snapshot(full_run.base)
    result = report.verify(full_run.root)
    assert result["representation_parser"] == {
        "package": "markdown-it-py",
        "version": "4.0.0",
        "preset": "commonmark",
    }
    assert [(r["capture"], r["field"]) for r in result["retained_prefix"]] == list(
        report.envelope.SEED_STAGES
    )
    assert result["retained_prefix"][-1]["original_response_root"] == report.envelope.V5_ROOT
    for capture in ("t059", "t060"):
        sources = json.loads(full_run.prepared[capture]["evidence_json"])["sources"]
        checked = report.load(full_run.root / f"{capture}--juror_2_json/validated.json")
        citation = checked["criteria"][0]["citations"][0]
        assert citation == {"source": "final", "quote": "PRIVATE final"}
        assert citation["quote"] not in sources["final"]
        assert report.jury.rendered_final_matches(sources["final"], citation["quote"])
    assert snapshot(full_run.base) == before


@pytest.mark.parametrize("kind", ["missing", "version", "package", "preset", "extra"])
def test_citation_parser_protocol_metadata_must_match(full_run, kind):
    def mutate(value):
        if kind == "missing":
            value.pop("representation_parser")
        else:
            value["representation_parser"][kind] = "drift"

    rewrite(full_run.root / "protocol.json", mutate)
    with pytest.raises(ValueError, match="representation_parser"):
        report.verify(full_run.root)


@pytest.mark.parametrize("installed", ["3.0.0", "4.0.1", "5.0.0", None])
def test_exact_installed_parser_required_even_with_forged_matching_protocol(
    full_run, monkeypatch, installed
):
    from importlib.metadata import PackageNotFoundError

    def version(package):
        assert package == "markdown-it-py"
        if installed is None:
            raise PackageNotFoundError(package)
        return installed

    monkeypatch.setattr(report, "version", version)
    rewrite(
        full_run.root / "protocol.json",
        lambda v: v["representation_parser"].update(version=installed),
    )
    with pytest.raises((ValueError, PackageNotFoundError)):
        report.verify(full_run.root)


@pytest.mark.parametrize(
    ("source", "quote", "accepted"),
    [
        ("final", "PRIVATE final", True),
        ("final", "**PRIVATE** final", True),
        ("final", "PRIVATE final with  two spaces and code", True),
        ("final", "Second block", True),
        ("final", "PRIVATE final with two spaces", False),
        ("final", "private final", False),
        ("final", "code\nSecond block", False),
        ("final", "hidden marker", False),
        ("final", "image suffix", False),
        ("tools", "PRIVATE final", False),
        ("messages", "PRIVATE final", False),
    ],
)
def test_full_readback_exact_rendered_final_not_fuzzy_or_cross_block(
    full_run, source, quote, accepted
):
    replace_adjudication(
        full_run, lambda v: v["criteria"][0].update(citations=[{"source": source, "quote": quote}])
    )
    before = snapshot(full_run.base)
    if accepted:
        report.verify(full_run.root)
    else:
        with pytest.raises(ValueError, match="unsupported citation"):
            report.verify(full_run.root)
    assert snapshot(full_run.base) == before


@pytest.mark.parametrize("ordinal", range(6))
@pytest.mark.parametrize("kind", ["omitted", "response", "request", "original_http"])
def test_every_runtime_pinned_prefix_position_required(full_run, ordinal, kind):
    active = report.envelope.SEED_STAGES[ordinal]
    name = "--".join(active)
    if kind == "omitted":
        rewrite(full_run.root / "protocol.json", lambda v: v["retained_prefix"].pop(ordinal))
    elif kind == "original_http":
        put(
            full_run.base / report.envelope.ORIGINAL_ROOTS[ordinal] / name / "http.json",
            {"status": 500},
        )
    else:
        path = (
            full_run.root / name / ("response.raw" if kind == "response" else "request.body.json")
        )
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError):
        report.verify(full_run.root)


@pytest.mark.parametrize("kind", ["empty", "not_prefix", "pin_count"])
def test_runtime_prefix_must_be_finite_ordered_and_fully_pinned(full_run, monkeypatch, kind):
    if kind == "empty":
        stages = ()
    elif kind == "not_prefix":
        stages = tuple(reversed(report.envelope.SEED_STAGES))
    else:
        stages = report.envelope.SEED_STAGES[:-1]
    monkeypatch.setattr(report.envelope, "SEED_STAGES", stages)
    # Reach prefix validation; omitted ledger rows cannot define the expected count.
    rewrite(
        full_run.root / "protocol.json",
        lambda v: v.update(
            planned_reused_responses=len(stages), planned_new_http_attempts=24 - len(stages)
        ),
    )
    with pytest.raises(ValueError, match="prefix"):
        report.verify(full_run.root)

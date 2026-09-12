"""Generated topology and deterministic validation tests, not live grading evidence."""

import ast
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "evals/dspx-jury/program"
spec = importlib.util.spec_from_file_location("compass_jury", ROOT / "scripts/compass_jury.py")
jury = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jury)


def test_dspx_materializes_three_independent_jurors_and_adjudicator():
    receipt = json.loads((PROGRAM / "generation.json").read_text())
    assert receipt["topology_execution"]["materialized"] is True
    assert receipt["topology_execution"]["status"] == "pipeline_materialized"
    intent = receipt["intent"]
    nodes = {node["id"]: node for node in intent["topology"]["modules"]}
    assert set(nodes) == {"juror_1", "juror_2", "juror_3", "adjudicator"}
    roles = set()
    for name in ("juror_1", "juror_2", "juror_3"):
        assert nodes[name]["primitive"] == "Predict"
        assert nodes[name]["signature"]["inputs"] == [
            "evidence_json",
            "rubric_json",
            "judgment_contract_json",
        ]
        assert nodes[name]["signature"]["outputs"] == [f"{name}_json"]
        roles.add(nodes[name]["role"])
    assert len(roles) == 1
    assert set(nodes["adjudicator"]["signature"]["inputs"]) == {
        "evidence_json",
        "rubric_json",
        "adjudication_contract_json",
        "juror_1_json",
        "juror_2_json",
        "juror_3_json",
    }
    edges = {(edge["from"], edge["to"]) for edge in intent["topology"]["edges"]}
    for name in ("juror_1", "juror_2", "juror_3"):
        assert {source for source, target in edges if target == name} == {"input"}
        assert (name, "adjudicator") in edges
    assert ("adjudicator", "output") in edges


def test_generated_sources_and_intent_match_recorded_hashes():
    receipt = json.loads((PROGRAM / "generation.json").read_text())
    for name, expected in receipt["source_sha256"].items():
        raw = (PROGRAM / name).read_bytes()
        assert jury.sha(raw) == expected
        compile(raw, name, "exec")
    assert jury.sha((PROGRAM.parent / "intent.yaml").read_bytes()) == receipt["intent_yaml_sha256"]
    assert receipt["live_model_called"] is False
    assert receipt["generation_provider"] == "stub"


def test_generated_juror_prompt_words_are_identical():
    tree = ast.parse((PROGRAM / "signature.py").read_text())
    roles = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    assert len(roles) == 4
    assert len({" ".join(ast.get_docstring(node).split()) for node in roles[:3]}) == 1


@pytest.fixture
def inputs(tmp_path):
    corpus = {
        "cases": [
            {
                "id": "example",
                "prompt": "Return 42.",
                "expected_output": {
                    "criteria": [{"id": "accurate", "description": "Return 42.", "required": True}]
                },
            }
        ]
    }
    capture = {
        "caseId": "example",
        "final": "42",
        "messages": [],
        "tools": [],
        "status": "executed",
        "notebookCreated": False,
        "arm": "candidate",
        "skill": True,
        "old_grades": {"accurate": False},
    }
    for name, value in (("corpus", corpus), ("capture", capture)):
        (tmp_path / f"{name}.json").write_text(json.dumps(value))
    return jury.prepare_inputs(
        tmp_path / "corpus.json", tmp_path / "capture.json", ROOT / "evals/dspx-jury/rubric.json"
    )


def judgment(inputs):
    contract = json.loads(inputs["judgment_contract_json"])
    return {
        "binding": contract["binding"],
        "criteria": [
            {
                "id": key,
                "verdict": "pass",
                "rationale": "Synthetic fixture.",
                "citations": [{"source": "final", "quote": "42"}],
            }
            for key in contract["criteria"]
        ],
    }


def test_preparation_excludes_labels_and_previous_grades(inputs):
    evidence = json.loads(inputs["evidence_json"])
    assert set(evidence["sources"]) == {
        "case_prompt",
        "final",
        "messages",
        "tools",
        "status",
        "notebook_created",
    }
    assert "old_grades" not in inputs["evidence_json"]
    assert '"arm"' not in inputs["evidence_json"]
    assert '"skill"' not in inputs["evidence_json"]
    assert evidence["sources"]["final"] == "42"
    assert json.loads(inputs["rubric_json"])["criteria"][0]["description"] == "Return 42."


def test_complete_valid_judgment(inputs):
    value = judgment(inputs)
    assert jury.validate_judgment(json.dumps(value), inputs) == value


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "unknown",
        "binding",
        "quote",
        "source",
        "no_citation",
        "verdict",
        "extra",
    ],
)
def test_bad_judgments_fail_without_regrading(inputs, mutation):
    value = judgment(inputs)
    first = value["criteria"][0]
    if mutation == "missing":
        value["criteria"].pop()
    elif mutation == "duplicate":
        value["criteria"].append(deepcopy(first))
    elif mutation == "unknown":
        first["id"] = "unknown"
    elif mutation == "binding":
        value["binding"]["source_sha256"] = "0" * 64
    elif mutation == "quote":
        first["citations"][0]["quote"] = "invented"
    elif mutation == "source":
        first["citations"][0]["source"] = "juror_opinion"
    elif mutation == "no_citation":
        first["citations"] = []
    elif mutation == "verdict":
        first["verdict"] = "approved"
    else:
        value["verified_live_model"] = True
    with pytest.raises(ValueError):
        jury.validate_judgment(json.dumps(value), inputs)


def test_empty_final_cannot_pass_delivery(inputs):
    value = judgment(inputs)
    evidence = json.loads(inputs["evidence_json"])
    evidence["sources"]["final"] = ""
    altered = {**inputs, "evidence_json": json.dumps(evidence)}
    for row in value["criteria"]:
        row["citations"] = [{"source": "status", "quote": "executed"}]
    with pytest.raises(ValueError, match="empty final"):
        jury.validate_judgment(json.dumps(value), altered)
    next(row for row in value["criteria"] if row["id"] == "final_delivery")["verdict"] = "fail"
    jury.validate_judgment(json.dumps(value), altered)


def test_insufficient_evidence_needs_reason_not_fake_citation(inputs):
    value = judgment(inputs)
    for row in value["criteria"]:
        row.update(verdict="insufficient_evidence", citations=[])
    jury.validate_judgment(json.dumps(value), inputs)
    value["criteria"][0]["rationale"] = ""
    with pytest.raises(ValueError, match="rationale"):
        jury.validate_judgment(json.dumps(value), inputs)


def test_adjudicator_must_truthfully_address_disagreement(inputs):
    original = {name: judgment(inputs) for name in jury.JURORS}
    original["juror_2_json"]["criteria"][0]["verdict"] = "fail"
    value = judgment(inputs)
    for row in value["criteria"]:
        row["disagreement"] = row["id"] == "accurate"
        row["addressed_jurors"] = [
            {
                "juror": name,
                "verdict": next(r["verdict"] for r in record["criteria"] if r["id"] == row["id"]),
                "assessment": "Synthetic assessment.",
            }
            for name, record in original.items()
        ]
    jury.validate_judgment(json.dumps(value), inputs, original)
    forged = deepcopy(value)
    forged["criteria"][0]["disagreement"] = False
    with pytest.raises(ValueError, match="disagreement"):
        jury.validate_judgment(json.dumps(forged), inputs, original)
    forged = deepcopy(value)
    forged["criteria"][0]["addressed_jurors"].pop()
    with pytest.raises(ValueError, match="three jurors"):
        jury.validate_judgment(json.dumps(forged), inputs, original)


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', "{}" * 300000])
def test_strict_json_rejects_ambiguous_or_oversize_input(raw):
    with pytest.raises(ValueError):
        jury.strict_json(raw)


@pytest.mark.parametrize(
    "model", ["glm-5.3-flash", "zai/glm-5.3-flash", "gpt-5.4", "stub/echo", None]
)
def test_no_silent_model_substitution(model):
    class OtherLM:
        pass

    lm = OtherLM()
    lm.model = model
    with pytest.raises(ValueError, match="no model substitution"):
        jury.evaluate({}, lm)


def test_strict_json_explicit_transport_limit_keeps_default_payload_cap():
    raw = json.dumps({"payload": "x" * jury.LIMIT})
    with pytest.raises(ValueError, match="byte limit"):
        jury.strict_json(raw)
    assert jury.strict_json(raw, max_bytes=len(raw))["payload"] == "x" * jury.LIMIT
    with pytest.raises(ValueError, match="byte limit"):
        jury.strict_json(raw, max_bytes=len(raw) - 1)
    with pytest.raises(ValueError, match="duplicate"):
        jury.strict_json('{"a":1,"a":2}', max_bytes=8_000_000)


@pytest.mark.parametrize("source", ["tools", "messages"])
@pytest.mark.parametrize("quote", ["first\nsecond", 'said "exactly"', "tab\tvalue"])
def test_citations_match_exact_decoded_nested_string_values(inputs, source, quote):
    evidence = json.loads(inputs["evidence_json"])
    evidence["sources"][source] = json.dumps(
        [{"nested": [None, 42, {"text": f"prefix {quote} suffix"}]}]
    )
    assert quote not in evidence["sources"][source]
    changed = {**inputs, "evidence_json": json.dumps(evidence)}
    value = judgment(inputs)
    value["criteria"][0]["citations"] = [{"source": source, "quote": quote}]
    raw = json.dumps(value)
    assert jury.validate_judgment(raw, changed) == value
    assert raw == json.dumps(value)  # Validation never rewrites the judgment.


@pytest.mark.parametrize("source", ["tools", "messages"])
@pytest.mark.parametrize(
    "kind", ["keys_only", "cross_leaf", "whitespace", "case", "recursive_json"]
)
def test_decoded_citations_do_not_repair_or_join(inputs, source, kind):
    quote = 'first\n"second"'
    values = {
        "keys_only": {quote: "unrelated"},
        "cross_leaf": ["first\n", '"second"'],
        "whitespace": ['first\n "second"'],
        "case": ['First\n"second"'],
        "recursive_json": [json.dumps({"text": quote})],
    }
    evidence = json.loads(inputs["evidence_json"])
    evidence["sources"][source] = json.dumps(values[kind])
    assert quote not in evidence["sources"][source]
    value = judgment(inputs)
    value["criteria"][0]["citations"] = [{"source": source, "quote": quote}]
    with pytest.raises(ValueError, match="unsupported citation"):
        jury.validate_judgment(json.dumps(value), {**inputs, "evidence_json": json.dumps(evidence)})


@pytest.mark.parametrize("source", ["final", "case_prompt", "status", "notebook_created"])
def test_no_json_decoding_for_other_citation_sources(source):
    assert not jury.citation_matches(source, json.dumps({"text": "first\nsecond"}), "first\nsecond")


@pytest.mark.parametrize("source", ["messages", "tools"])
def test_original_serialized_substring_still_matches(source):
    text = json.dumps([{"text": "first\nsecond"}])
    assert jury.citation_matches(source, text, "first\\nsecond")


def test_third_juror_quote_representation_with_synthetic_source(inputs):
    quote = "A wrong path is not a\nreason to create a replacement decision silently."
    tools = jury.canonical([{}, {}, {}, {"result": {"content": [{"text": quote}]}}])
    evidence = jury.strict_json(inputs["evidence_json"])
    evidence["sources"]["tools"] = tools
    changed = {**inputs, "evidence_json": jury.canonical(evidence)}
    record = judgment(inputs)
    record["criteria"][0]["citations"] = [{"source": "tools", "quote": quote}]
    assert quote not in tools
    assert quote in jury.strict_json(tools)[3]["result"]["content"][0]["text"]
    assert jury.validate_judgment(jury.canonical(record), changed) == record


@pytest.mark.parametrize(
    "roles",
    [
        ["juror_1_", "juror_2_", "juror_3_"],
        ["juror_1_json", "juror_2_", "juror_3_json"],
    ],
)
def test_role_aliases_are_lookup_only_and_preserve_original_rows(inputs, roles):
    previous = {name: judgment(inputs) for name in jury.JURORS}
    value = judgment(inputs)
    for row in value["criteria"]:
        row.update(
            disagreement=False,
            addressed_jurors=[
                {"juror": role, "verdict": "pass", "assessment": "Original unchanged assessment."}
                for role in roles
            ],
        )
    raw = json.dumps(value)
    assert jury.validate_judgment(raw, inputs, previous) == value
    assert json.dumps(value) == raw
    assert [r["juror"] for r in value["criteria"][0]["addressed_jurors"]] == roles


@pytest.mark.parametrize(
    "mutation", ["unknown", "duplicate", "mixed_duplicate", "missing", "verdict"]
)
def test_alias_roles_do_not_allow_invalid_adjudication(inputs, mutation):
    previous = {name: judgment(inputs) for name in jury.JURORS}
    value = judgment(inputs)
    for row in value["criteria"]:
        row.update(
            disagreement=False,
            addressed_jurors=[
                {"juror": name, "verdict": "pass", "assessment": "Keep exact text."}
                for name in ("juror_1_", "juror_2_", "juror_3_")
            ],
        )
    addressed = value["criteria"][0]["addressed_jurors"]
    if mutation == "unknown":
        addressed[0]["juror"] = "juror_1"
    elif mutation == "duplicate":
        addressed[1]["juror"] = "juror_1_"
    elif mutation == "mixed_duplicate":
        addressed[1]["juror"] = "juror_1_json"
    elif mutation == "missing":
        addressed.pop()
    else:
        addressed[0]["verdict"] = "fail"
    raw = json.dumps(value)
    with pytest.raises(ValueError):
        jury.validate_judgment(raw, inputs, previous)
    assert json.dumps(value) == raw


@pytest.mark.parametrize(
    "text,quote",
    [
        ("**Alpha** is *exact*.", "Alpha is exact."),
        ("**Use** `*literal*` and `a  b`.", "Use *literal* and a  b."),
        ("**Read** [the record](https://example.invalid).", "Read the record."),
        ("**Alpha**\nBeta", "Alpha\nBeta"),
        ("**Alpha**  \nBeta", "Alpha\nBeta"),
        ("# **Alpha** and Beta", "Alpha and Beta"),
    ],
)
def test_final_exact_commonmark_inline_text(inputs, text, quote):
    pytest.importorskip("markdown_it")
    assert quote not in text
    evidence = json.loads(inputs["evidence_json"])
    evidence["sources"]["final"] = text
    changed = {**inputs, "evidence_json": json.dumps(evidence)}
    value = judgment(inputs)
    for row in value["criteria"]:
        row["citations"] = [{"source": "final", "quote": quote}]
    raw = json.dumps(value)
    assert jury.validate_judgment(raw, changed) == value
    assert raw == json.dumps(value)


@pytest.mark.parametrize(
    "text,quote",
    [
        ("**Alpha** <span>Beta</span>", "Alpha Beta"),
        ("**Alpha** ![Beta](image.png)", "Alpha Beta"),
        ("**Alpha** ![Beta](image.png)", "Alpha "),
        ("<div>**Alpha** Beta</div>", "Alpha Beta"),
        ("**Alpha**\n\nBeta", "Alpha\nBeta"),
        ("**Alpha**\n\nBeta", "Alpha Beta"),
        ("**Alpha** Beta", "Alpha Gamma"),
        ("**Alpha** Beta", "alpha Beta"),
        ("**Alpha**  Beta", "Alpha Beta"),
        ("**Alpha**\nBeta", "Alpha Beta"),
        ("**Use** `*literal*`.", "Use literal."),
        ("**Use** `a  b`.", "Use a b."),
        ("```\n**Alpha** Beta\n```", "Alpha Beta"),
    ],
)
def test_rendered_final_rejects_lossy_or_inexact_matching(text, quote):
    pytest.importorskip("markdown_it")
    assert quote not in text
    assert not jury.citation_matches("final", text, quote)


@pytest.mark.parametrize("source", ["status", "case_prompt", "notebook_created"])
def test_commonmark_fallback_only_applies_to_final(source):
    assert not jury.citation_matches(source, "**Alpha** Beta", "Alpha Beta")


def test_commonmark_unavailable_fails_closed_but_raw_still_works(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "markdown_it", None)
    assert not jury.citation_matches("final", "**Alpha** Beta", "Alpha Beta")
    assert jury.citation_matches("final", "**Alpha** Beta", "**Alpha** Beta")


def test_juror_quote_matches_synthetic_rendered_final(inputs):
    pytest.importorskip("markdown_it")
    quote = "No supplied decision record file is readable from the working directory"
    final = "**No supplied decision record file** is readable from the working directory"
    evidence = jury.strict_json(inputs["evidence_json"])
    evidence["sources"]["final"] = final
    changed = {**inputs, "evidence_json": jury.canonical(evidence)}
    value = judgment(inputs)
    for row in value["criteria"]:
        row["citations"] = [{"source": "final", "quote": quote}]
    assert quote not in final
    assert jury.rendered_final_matches(final, quote)
    assert jury.validate_judgment(jury.canonical(value), changed) == value

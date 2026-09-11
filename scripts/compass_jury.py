"""COMPASS-specific inputs and validation around a DSPx-generated DSPy program.

No provider construction, credential handling, paid calls or automatic retries here.
The caller supplies the already configured LM; live execution remains a separate gate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "evals/dspx-jury/program"
JURORS = ("juror_1_json", "juror_2_json", "juror_3_json")
OUTPUTS = (*JURORS, "adjudication_json")
LIMIT = 512_000


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"non-finite JSON value: {value}")

    if len(raw.encode("utf-8")) > LIMIT:
        raise ValueError("JSON byte limit exceeded; no truncation")
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    canonical(result)  # Reject overflowing floats and unencodable values.
    return result


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("input byte limit exceeded")
    return raw, strict_json(raw.decode("utf-8"))


def prepare_inputs(corpus_path, capture_path, rubric_path):
    corpus_raw, corpus = read_json(corpus_path)
    capture_raw, capture = read_json(capture_path)
    rubric_raw, policy = read_json(rubric_path)
    cases = {case["id"]: case for case in corpus["cases"]}
    if len(cases) != len(corpus["cases"]):
        raise ValueError("duplicate corpus case")
    case = cases[capture["caseId"]]
    if not isinstance(capture["final"], str):
        raise ValueError("capture final must be text")
    if not all(isinstance(capture[key], list) for key in ("messages", "tools")):
        raise ValueError("capture messages/tools must be lists")
    sources = {
        "case_prompt": case["prompt"],
        "final": capture["final"],
        "messages": canonical(capture["messages"]),
        "tools": canonical(capture["tools"]),
        "status": capture["status"],
        "notebook_created": canonical(capture["notebookCreated"]),
    }
    criteria = [
        {**item, "dimension": "original_quality"} for item in case["expected_output"]["criteria"]
    ] + policy["common_criteria"]
    ids = [item["id"] for item in criteria]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate criterion")
    rubric = {"version": policy["version"], "rules": policy["rules"], "criteria": criteria}
    binding = {
        "source_sha256": sha(capture_raw),
        "corpus_sha256": sha(corpus_raw),
        "rubric_file_sha256": sha(rubric_raw),
        "rubric_sha256": sha(canonical(rubric).encode("utf-8")),
    }
    contract = {
        "binding": binding,
        "criteria": ids,
        "shape": {
            "binding": "copy binding exactly",
            "criteria": [
                {
                    "id": "exact criterion id",
                    "verdict": "pass|fail|insufficient_evidence",
                    "rationale": "concise evidence-based reason",
                    "citations": [
                        {"source": "key from evidence.sources", "quote": "exact substring"}
                    ],
                }
            ],
        },
        "rules": "Exactly these keys. Every criterion once. Pass/fail needs citations. "
        "An empty final must fail final_delivery; cite status or messages if needed.",
    }
    adjudication = {
        **contract,
        "additional_row_fields": {
            "disagreement": "boolean: do the three juror verdicts differ?",
            "addressed_jurors": [
                {
                    "juror": "juror_1_json|juror_2_json|juror_3_json",
                    "verdict": "the juror's exact verdict",
                    "assessment": "your reasoned assessment",
                }
            ],
        },
        "rules": contract["rules"] + " Address all three jurors on every criterion. "
        "Resolve against original evidence, not majority vote; allow insufficient_evidence.",
    }
    result = {
        "evidence_json": canonical(
            {
                "binding": binding,
                "sources": sources,
                "provenance": "historical_capture_not_authenticated_provider_execution",
                "projection": "prompt/final/messages/tools/status/notebookCreated; "
                "top-level arm/id/skill and old grades excluded, no content truncation; "
                "evidence content may reveal treatment",
            }
        ),
        "rubric_json": canonical(rubric),
        "judgment_contract_json": canonical(contract),
        "adjudication_contract_json": canonical(adjudication),
    }
    if len(canonical(result).encode("utf-8")) > LIMIT:
        raise ValueError("combined program input byte limit exceeded; no truncation")
    return result


def validate_judgment(raw, inputs, previous=None):
    value = strict_json(raw)
    contract = strict_json(inputs["judgment_contract_json"])
    sources = strict_json(inputs["evidence_json"])["sources"]
    if set(value) != {"binding", "criteria"} or value["binding"] != contract["binding"]:
        raise ValueError("judgment binding/schema mismatch")
    expected = set(contract["criteria"])
    if not isinstance(value["criteria"], list):
        raise ValueError("criteria must be a list")
    seen = set()
    for row in value["criteria"]:
        keys = {"id", "verdict", "rationale", "citations"}
        if previous is not None:
            keys |= {"disagreement", "addressed_jurors"}
        if not isinstance(row, dict) or set(row) != keys:
            raise ValueError("criterion schema mismatch")
        key = row["id"]
        if not isinstance(key, str) or key not in expected or key in seen:
            raise ValueError("unknown/duplicate criterion")
        seen.add(key)
        if row["verdict"] not in ("pass", "fail", "insufficient_evidence"):
            raise ValueError("invalid verdict")
        if not isinstance(row["rationale"], str) or not row["rationale"].strip():
            raise ValueError("rationale required")
        if not isinstance(row["citations"], list):
            raise ValueError("citations must be a list")
        if row["verdict"] != "insufficient_evidence" and not row["citations"]:
            raise ValueError("pass/fail requires citations")
        for citation in row["citations"]:
            if not isinstance(citation, dict) or set(citation) != {"source", "quote"}:
                raise ValueError("citation schema mismatch")
            source, quote = citation["source"], citation["quote"]
            if not isinstance(source, str) or not isinstance(quote, str) or not quote.strip():
                raise ValueError("citation text required")
            if source not in sources or quote not in sources[source]:
                raise ValueError("unsupported citation")
        if key == "final_delivery" and not sources["final"].strip() and row["verdict"] != "fail":
            raise ValueError("empty final must fail delivery")
        if previous is not None:
            _validate_disagreement(row, previous)
    if seen != expected:
        raise ValueError("criterion omission")
    return value


def _validate_disagreement(row, previous):
    original = {
        name: next(item["verdict"] for item in judgment["criteria"] if item["id"] == row["id"])
        for name, judgment in previous.items()
    }
    if set(original) != set(JURORS):
        raise ValueError("complete three-juror record required")
    if type(row["disagreement"]) is not bool or row["disagreement"] != (
        len(set(original.values())) > 1
    ):
        raise ValueError("incorrect disagreement flag")
    addressed = row["addressed_jurors"]
    if not isinstance(addressed, list) or len(addressed) != 3:
        raise ValueError("must address three jurors")
    seen = set()
    for item in addressed:
        if not isinstance(item, dict) or set(item) != {"juror", "verdict", "assessment"}:
            raise ValueError("addressed juror schema mismatch")
        name = item["juror"]
        if not isinstance(name, str) or name in seen or name not in original:
            raise ValueError("unknown/duplicate juror")
        if (
            item["verdict"] != original[name]
            or not isinstance(item["assessment"], str)
            or not item["assessment"].strip()
        ):
            raise ValueError("juror verdict/assessment mismatch")
        seen.add(name)


def load_program():
    receipt = json.loads((PROGRAM / "generation.json").read_text())
    for name, expected in receipt["source_sha256"].items():
        if sha((PROGRAM / name).read_bytes()) != expected:
            raise ValueError("normalized generated source drift")
    if any(name in sys.modules for name in ("module", "signature", "metadata")):
        raise ValueError("use a fresh Python process; generated module names already loaded")
    sys.path.insert(0, str(PROGRAM))
    spec = importlib.util.spec_from_file_location("compass_generated_jury", PROGRAM / "program.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(inputs, lm, *, allow_stub=False, stage_callback=None):
    """Run the real generated graph with per-stage validation and supplied LM.

    This function does not authorize or construct a provider and authenticates no
    backend identity. The live runner must separately bound calls, spending and retries.
    """
    requested_model = getattr(lm, "model", None)
    allowed = {"glm-5.3", "zai/glm-5.3", "openai/glm-5.3"}
    if requested_model not in allowed and not (allow_stub and requested_model == "stub/echo"):
        raise ValueError("explicit glm-5.3 required; no model substitution")
    import dspy

    observed = {}
    started = set()
    bound_inputs = inputs

    class ValidatingAdapter(dspy.JSONAdapter):
        def __call__(self, lm, lm_kwargs, signature, demos, inputs):
            (field,) = signature.output_fields
            if field in started or len(observed) >= len(OUTPUTS):
                raise ValueError("duplicate/excess program stage")
            if field != OUTPUTS[len(observed)]:
                raise ValueError("unexpected program stage/order")
            started.add(field)
            if stage_callback is not None:
                stage_callback(field)
            result = super().__call__(lm, lm_kwargs, signature, demos, inputs)
            if len(result) != 1 or set(result[0]) != {field}:
                raise ValueError("one exact output required")
            previous = observed if field == "adjudication_json" else None
            observed[field] = validate_judgment(result[0][field], bound_inputs, previous)
            return result

    program = load_program().build_program()
    with dspy.context(lm=lm, adapter=ValidatingAdapter(use_native_function_calling=False)):
        result = program(**inputs)
    return {
        "requested_model": requested_model,
        "provider_model_authenticated": False,
        "judgments": observed,
        "raw_outputs": dict(result),
        "trace": program._last_runtime_trace,
        "semantic_correctness_established": False,
        "action_permission": "not_granted",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--rubric", type=Path, default=ROOT / "evals/dspx-jury/rubric.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = prepare_inputs(args.corpus, args.capture, args.rubric)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(canonical(inputs) + "\n")
    print(canonical({"prepared": True, "model_invoked": False, "output": str(args.output)}))


if __name__ == "__main__":
    main()

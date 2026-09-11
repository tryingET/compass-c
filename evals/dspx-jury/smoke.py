"""Execute the real generated DSPy graph with DSPx's credential-free stub provider."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from compass_jury import JURORS, canonical, evaluate, prepare_inputs  # noqa: E402


def smoke(invalid_stage=None):
    from dspx.dspy_typed_lm import DSPyTypedLMAdapter
    from dspx.stub_provider import StubProvider

    with tempfile.TemporaryDirectory(prefix="compass-jury-smoke-") as temporary:
        root = Path(temporary)
        corpus = {
            "cases": [
                {
                    "id": "synthetic",
                    "prompt": "Return 42.",
                    "expected_output": {
                        "criteria": [{"id": "accurate", "description": "Return 42."}]
                    },
                }
            ]
        }
        capture = {
            "caseId": "synthetic",
            "final": "42",
            "messages": [],
            "tools": [],
            "status": "executed",
            "notebookCreated": False,
        }
        policy = {
            "version": "synthetic-v1",
            "rules": ["Synthetic fixture, not model evidence."],
            "common_criteria": [],
        }
        for name, value in (("corpus", corpus), ("capture", capture), ("rubric", policy)):
            (root / f"{name}.json").write_text(canonical(value))
        inputs = prepare_inputs(root / "corpus.json", root / "capture.json", root / "rubric.json")

    binding = json.loads(inputs["judgment_contract_json"])["binding"]
    responses = {}
    for index, name in enumerate(JURORS):
        verdict = "insufficient_evidence" if index == 1 else "pass"
        responses[name] = canonical(
            {
                "binding": binding,
                "criteria": [
                    {
                        "id": "accurate",
                        "verdict": verdict,
                        "rationale": f"Synthetic juror {index + 1} fixture, not a model judgment.",
                        "citations": [{"source": "final", "quote": "42"}],
                    }
                ],
            }
        )
    responses["adjudication_json"] = canonical(
        {
            "binding": binding,
            "criteria": [
                {
                    "id": "accurate",
                    "verdict": "pass",
                    "rationale": "Synthetic adjudicator fixture.",
                    "citations": [{"source": "final", "quote": "42"}],
                    "disagreement": True,
                    "addressed_jurors": [
                        {
                            "juror": name,
                            "verdict": json.loads(responses[name])["criteria"][0]["verdict"],
                            "assessment": "Synthetic assessment of this juror.",
                        }
                        for name in JURORS
                    ],
                }
            ],
        }
    )
    if invalid_stage:
        value = json.loads(responses[invalid_stage])
        value["criteria"] = []
        responses[invalid_stage] = canonical(value)
    provider = StubProvider(explicit_response_text=canonical(responses))
    if invalid_stage:
        try:
            evaluate(inputs, DSPyTypedLMAdapter(provider), allow_stub=True)
        except ValueError as exc:
            assert "criterion omission" in str(exc)
        else:
            raise AssertionError("invalid judgment accepted")
        expected_calls = 1 if invalid_stage == "juror_1_json" else 4
        assert provider.attempt_total == expected_calls
        return {
            "status": "pass",
            "negative_test": invalid_stage,
            "rejected_invalid_judgment": True,
            "provider": "stub",
            "provider_invocations": expected_calls,
            "paid_model_calls": 0,
        }
    result = evaluate(inputs, DSPyTypedLMAdapter(provider), allow_stub=True)
    calls = result["trace"]["module_calls"]
    assert provider.attempt_total == 4
    assert [call["module_id"] for call in calls] == ["juror_1", "juror_2", "juror_3", "adjudicator"]
    for call in calls[:3]:
        assert set(call["inputs"]) == {"evidence_json", "rubric_json", "judgment_contract_json"}
        assert call["inputs"]["rubric_json"] == inputs["rubric_json"]
        assert call["inputs"]["evidence_json"] == inputs["evidence_json"]
    for name in JURORS:
        assert calls[3]["inputs"][name] == responses[name]
    assert result["judgments"]["adjudication_json"]["criteria"][0]["disagreement"] is True
    return {
        "status": "pass",
        "provider": "stub",
        "actual_generated_graph_executed": True,
        "provider_invocations": provider.attempt_total,
        "paid_model_calls": 0,
        "juror_inputs_equal": True,
        "peer_judgments_hidden_from_jurors": True,
        "adjudicator_received_three_judgments": True,
        "semantic_correctness_established": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--invalid-stage", choices=["juror_1_json", "adjudication_json"])
    args = parser.parse_args()
    print(canonical(smoke(args.invalid_stage)))

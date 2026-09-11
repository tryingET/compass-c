"""Synthetic fixtures for the source-owned paired reporting adapter; no models."""

import json

import pytest

from scripts.report_glm_dogfood import build_results


def fixture(root):
    def write(name, value):
        (root / name).write_text(json.dumps(value))

    corpus = {
        "schema_version": 1,
        "status": "frozen_development_only",
        "authorship": "synthetic test",
        "cases": [
            {
                "id": "one",
                "kind": "negative",
                "split": "development",
                "prompt": "Test",
                "expected_compass": False,
                "forbidden_primary_skill": "compass",
                "expected_output": {
                    "rubric_version": 1,
                    "criteria": [
                        {"id": "first", "description": "Pass only when first", "required": True},
                        {"id": "second", "description": "Pass only when second", "required": True},
                    ],
                },
            }
        ],
    }
    schedule = [
        {"id": f"{phase}-{arm}", "phase": phase, "arm": arm, "caseId": "one"}
        for phase in ("aa", "ab")
        for arm in ("baseline", "candidate")
    ]
    write(
        "protocol.json",
        {"schedule": schedule, "piVersion": "fixture", "skillTreeSha256": "fixture"},
    )
    write("corpus.json", corpus)
    for item in schedule:
        write(
            item["id"] + ".json",
            {"status": "executed", "tools": [], "notebookCreated": False, "durationMs": 1},
        )
        write(
            item["id"] + ".grade.json",
            {
                "criteria": [
                    {"id": "first", "pass": item["arm"] == "candidate", "evidence": "synthetic"},
                    {"id": "second", "pass": True, "evidence": "synthetic"},
                ]
            },
        )


def test_uses_core_report_and_marks_synthetic_provenance(tmp_path):
    fixture(tmp_path)
    results, report, metrics = build_results(tmp_path, "A/B", evidence_kind="synthetic_fixture")
    assert results["evidence_kind"] == "synthetic_fixture"
    assert results["baseline"]["revision"] != results["candidate"]["revision"]
    assert report["action_permission"] == "not_granted"
    assert len(metrics["captures"]) == 2
    assert len(metrics["artifact_sha256"]) == 4


def test_missing_capture_or_criterion_is_not_filled(tmp_path):
    fixture(tmp_path)
    (tmp_path / "ab-baseline.json").unlink()
    with pytest.raises(FileNotFoundError):
        build_results(tmp_path, "A/B", evidence_kind="synthetic_fixture")


def test_indeterminate_execution_cannot_become_quality_evidence(tmp_path):
    fixture(tmp_path)
    (tmp_path / "ab-baseline.json").write_text('{"status":"provider_indeterminate"}')
    with pytest.raises(ValueError, match="Indeterminate"):
        build_results(tmp_path, "A/B", evidence_kind="synthetic_fixture")


@pytest.mark.parametrize("kind", ["duplicate_keys", "truncated"])
def test_unverified_host_claim_rejects_bad_raw_judgment(tmp_path, kind):
    fixture(tmp_path)  # Artificial input claiming host provenance, not an actual observation.
    for arm in ("baseline", "candidate"):
        grade = (tmp_path / f"ab-{arm}.grade.json").read_text()
        raw = {"text": grade, "stopReason": "stop"}
        if arm == "baseline":
            if kind == "duplicate_keys":
                raw["text"] = '{"criteria": [], "criteria": []}'
            else:
                raw["stopReason"] = "length"
        (tmp_path / f"ab-{arm}.judge.json").write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="reconciliation|Incomplete judge"):
        build_results(tmp_path, "A/B", evidence_kind="host_observation")

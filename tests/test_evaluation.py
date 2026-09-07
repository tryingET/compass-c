"""Synthetic score fixtures exercise arithmetic; they are not host evaluations."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from compass_c.core import CompassError
from compass_c.evaluation import evaluate

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(corpus: dict) -> str:
    encoded = json.dumps(corpus, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@pytest.fixture
def corpus() -> dict:
    return json.loads((ROOT / "skills/compass/evals/cases.json").read_text(encoding="utf-8"))


def synthetic_runs(corpus: dict) -> dict:
    results = []
    for case in corpus["cases"]:
        primary = case.get("expected_skill", "compass" if case.get("expected_compass") else None)
        results.append(
            {
                "case_id": case["id"],
                "compass_selected": case.get("expected_compass", primary == "compass"),
                "primary_skill": primary,
                "scores": {
                    criterion["id"]: True
                    for criterion in case["expected_output"]["criteria"]
                },
                "response_ref": f"synthetic-fixture:{case['id']}",
            }
        )
    return {
        "schema_version": 1,
        "comparison": "A/B",
        "evidence_kind": "synthetic_fixture",
        "corpus_sha256": fingerprint(corpus),
        "host": {"name": "synthetic", "model": "none", "configuration": "unit-test-only"},
        "grader": "synthetic-test-fixture",
        "baseline": {"revision": "synthetic-baseline", "results": copy.deepcopy(results)},
        "candidate": {"revision": "synthetic-candidate", "results": copy.deepcopy(results)},
    }


def fail_case(runs: dict, arm: str, index: int) -> None:
    row = runs[arm]["results"][index]
    row["scores"][next(iter(row["scores"]))] = False


def test_complete_paired_report_retains_provenance_and_boundaries(corpus: dict) -> None:
    runs = synthetic_runs(corpus)
    before = copy.deepcopy((corpus, runs))
    report = evaluate(corpus, runs)
    assert evaluate(corpus, runs) == report
    assert (corpus, runs) == before
    assert report["schema_version"] == 1
    assert report["comparison"] == "A/B"
    assert report["evidence"]["kind"] == "synthetic_fixture"
    assert report["evidence"]["corpus_visibility"] == "author_visible_development"
    assert report["evidence"]["behavioral_improvement_established"] is False
    assert report["permission_granted"] is False
    assert report["provenance"]["corpus_sha256"] == fingerprint(corpus)
    assert report["provenance"]["host"] == runs["host"]
    assert report["provenance"]["grader"] == runs["grader"]
    assert report["provenance"]["baseline_revision"] == runs["baseline"]["revision"]
    assert report["provenance"]["candidate_revision"] == runs["candidate"]["revision"]
    assert report["case_success"]["pairs"] == 24
    assert report["case_success"]["baseline_rate"] == 1.0
    assert report["case_success"]["candidate_rate"] == 1.0
    assert report["case_success"]["delta"] == 0.0
    assert report["case_success"]["exact_sign_test"]["two_sided_p"] == 1.0
    assert set(report["by_kind"]) == {"positive", "negative", "overlap", "pressure"}
    assert report["regressions"] == []


def test_exact_paired_uncertainty_uses_cases_not_pooled_criteria(corpus: dict) -> None:
    runs = synthetic_runs(corpus)
    for index in range(6):
        fail_case(runs, "baseline", index)
    report = evaluate(corpus, runs)
    summary = report["case_success"]
    assert summary["baseline_passed"] == 18
    assert summary["candidate_passed"] == 24
    assert summary["delta"] == 0.25
    assert summary["improved"] == 6
    assert summary["regressed"] == 0
    assert summary["discordance_rate"] == 0.25
    assert summary["exact_sign_test"]["discordant_pairs"] == 6
    assert summary["exact_sign_test"]["two_sided_p"] == 0.03125
    assert report["criteria"]["compares_options"]["pairs"] == 2
    assert report["criteria"]["compares_options"]["delta"] == 1.0
    assert report["evidence"]["behavioral_improvement_established"] is False


def test_aa_retains_disagreement_despite_zero_net_delta(corpus: dict) -> None:
    runs = synthetic_runs(corpus)
    runs["comparison"] = "A/A"
    runs["candidate"]["revision"] = runs["baseline"]["revision"]
    fail_case(runs, "baseline", 0)
    fail_case(runs, "candidate", 1)
    report = evaluate(corpus, runs)
    assert report["comparison"] == "A/A"
    assert report["case_success"]["delta"] == 0
    assert report["case_success"]["improved"] == 1
    assert report["case_success"]["regressed"] == 1
    assert report["case_success"]["discordance_rate"] == pytest.approx(2 / 24)
    assert report["case_success"]["exact_sign_test"]["two_sided_p"] == 1


def test_routing_failures_and_hidden_criterion_regressions_are_named(corpus: dict) -> None:
    runs = synthetic_runs(corpus)
    # A criterion regression must remain visible even when the case already failed.
    fail_case(runs, "baseline", 0)
    fail_case(runs, "candidate", 0)
    criterion = list(runs["candidate"]["results"][0]["scores"])[1]
    runs["candidate"]["results"][0]["scores"][criterion] = False
    runs["candidate"]["results"][8]["compass_selected"] = True
    runs["candidate"]["results"][12]["primary_skill"] = "compass"
    report = evaluate(corpus, runs)
    assert report["routing"]["candidate_passed"] == 22
    assert report["case_success"]["candidate_passed"] == 21
    assert report["rubric"]["candidate_passed"] == 23
    by_case = {item["case_id"]: item for item in report["regressions"]}
    assert by_case[corpus["cases"][0]["id"]]["criteria"] == [criterion]
    assert by_case[corpus["cases"][8]["id"]]["routing"] is True
    assert by_case[corpus["cases"][12]["id"]]["routing"] is True
    assert report["by_kind"]["negative"]["routing"]["regressed"] == 1
    assert report["by_kind"]["overlap"]["routing"]["regressed"] == 1


def test_case_order_is_paired_by_id(corpus: dict) -> None:
    runs = synthetic_runs(corpus)
    expected = evaluate(corpus, runs)
    runs["candidate"]["results"].reverse()
    assert evaluate(corpus, runs) == expected


def test_repo_maintainer_corpus_preserves_owner_routing() -> None:
    path = ROOT / ".pi/skills/compass-c-maintainer/evals/cases.json"
    corpus = json.loads(path.read_text(encoding="utf-8"))
    runs = synthetic_runs(corpus)
    runs["candidate"]["results"][0]["primary_skill"] = "compass"
    report = evaluate(corpus, runs)
    assert report["evidence"]["corpus_visibility"] == "author_visible_development"
    assert report["routing"]["regressed"] == 1
    assert report["case_success"]["pairs"] == 8


def test_declared_holdout_and_host_metadata_are_not_verified_independence(corpus: dict) -> None:
    corpus["status"] = "frozen_independent_holdout"
    corpus["authorship"] = "Synthetic metadata exercising a declared holdout contract."
    for case in corpus["cases"]:
        case["split"] = "holdout"
    runs = synthetic_runs(corpus)
    runs["evidence_kind"] = "host_observation"
    report = evaluate(corpus, runs)
    assert report["evidence"]["corpus_visibility"] == "independent_holdout_declared"
    assert report["evidence"]["provenance_verified"] is False
    assert report["evidence"]["behavioral_improvement_established"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c, r: r.update(schema_version=True),
        lambda c, r: r.update(comparison="AB"),
        lambda c, r: r.update(evidence_kind="verified_improvement"),
        lambda c, r: r.update(corpus_sha256="0" * 64),
        lambda c, r: r.update(host={}),
        lambda c, r: r["host"].update(configuration=" "),
        lambda c, r: r.update(grader=""),
        lambda c, r: r["baseline"].update(revision=""),
        lambda c, r: r.update(comparison="A/A"),
        lambda c, r: r["candidate"].update(revision=r["baseline"]["revision"]),
        lambda c, r: r["candidate"]["results"].pop(),
        lambda c, r: r["candidate"]["results"].append(r["candidate"]["results"][0]),
        lambda c, r: r["baseline"]["results"][0].update(case_id="unknown_case"),
        lambda c, r: r["baseline"]["results"][0].update(response_ref=""),
        lambda c, r: r["baseline"]["results"][0].update(primary_skill=[]),
        lambda c, r: r["baseline"]["results"][0].update(compass_selected=1),
        lambda c, r: r["baseline"]["results"][0]["scores"].update(compares_options=1),
        lambda c, r: r["baseline"]["results"][0]["scores"].update(compares_options="false"),
        lambda c, r: r["baseline"]["results"][0]["scores"].update(unknown=True),
        lambda c, r: r["baseline"]["results"][0]["scores"].pop("compares_options"),
        lambda c, r: r["candidate"].update(results=[]),
        lambda c, r: r["candidate"].update(results=[None]),
        lambda c, r: r["candidate"].update(results={}),
    ],
)
def test_rejects_unusable_or_unpaired_observations(corpus: dict, mutation) -> None:
    runs = synthetic_runs(corpus)
    mutation(corpus, runs)
    with pytest.raises(CompassError) as caught:
        evaluate(corpus, runs)
    assert caught.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c.update(schema_version=True),
        lambda c: c.update(status="unfrozen"),
        lambda c: c.update(cases=[]),
        lambda c: c["cases"].append(c["cases"][0]),
        lambda c: c["cases"][0].update(expected_compass=1),
        lambda c: c["cases"][0].update(kind="unknown"),
        lambda c: c["cases"][0]["expected_output"].update(rubric_version=True),
        lambda c: c["cases"][0]["expected_output"].update(criteria=[]),
        lambda c: c["cases"][0]["expected_output"]["criteria"].append(
            c["cases"][0]["expected_output"]["criteria"][0]
        ),
        lambda c: c["cases"][0]["expected_output"]["criteria"][0].update(required=1),
        lambda c: c["cases"][0]["expected_output"]["criteria"][0].update(description=" "),
        lambda c: c.update(status="frozen_independent_holdout"),
    ],
)
def test_rejects_invalid_corpus_even_with_matching_digest(corpus: dict, mutation) -> None:
    runs = synthetic_runs(corpus)
    mutation(corpus)
    runs["corpus_sha256"] = fingerprint(corpus)
    with pytest.raises(CompassError) as caught:
        evaluate(corpus, runs)
    assert caught.value.code == "INVALID_INPUT"


@pytest.mark.parametrize("corpus,runs", [(None, {}), ([], {}), ({}, None), ({}, []), ({}, {})])
def test_malformed_documents_have_stable_errors(corpus, runs) -> None:
    with pytest.raises(CompassError) as caught:
        evaluate(corpus, runs)
    assert caught.value.code == "INVALID_INPUT"

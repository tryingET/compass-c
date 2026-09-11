"""Synthetic transformation checks; neither fixtures nor passes are model evidence."""

import copy
import json

import pytest

from scripts.report_glm_dogfood import verify_judgment_transform

TRIAL = {"tools": [], "notebookCreated": False}


def row(identifier, passed=True):
    return {"id": identifier, "pass": passed, "evidence": "synthetic retained evidence"}


@pytest.mark.parametrize("change", ["pass", "evidence"])
def test_changed_required_judgment_is_rejected(change):
    original = {"criteria": [row("a")]}
    changed = copy.deepcopy(original)
    changed["criteria"][0][change] = False if change == "pass" else "invented evidence"
    with pytest.raises(ValueError, match="changed"):
        verify_judgment_transform(json.dumps(original), changed, {"a"}, TRIAL)


def test_duplicate_arrays_are_losslessly_accounted_for():
    raw = (
        '{"criteria":['
        + json.dumps(row("a"))
        + '],"criteria":['
        + json.dumps(row("b", False))
        + "]}"
    )
    grade = {"criteria": [row("a"), row("b", False)]}
    with pytest.raises(ValueError, match="reconciliation"):
        verify_judgment_transform(raw, grade, {"a", "b"}, TRIAL)
    checked = verify_judgment_transform(raw, grade, {"a", "b"}, TRIAL, {})
    assert checked["criteria_arrays_checked"] == 2
    assert checked["required_judgments_checked"] == 2


def test_conflicting_duplicate_required_judgments_are_never_selected():
    raw = (
        '{"criteria":['
        + json.dumps(row("a"))
        + '],"criteria":['
        + json.dumps(row("a", False))
        + "]}"
    )
    with pytest.raises(ValueError, match="Repeated required"):
        verify_judgment_transform(raw, {"criteria": [row("a")]}, {"a"}, TRIAL, {})


def test_only_identified_unknown_ids_may_be_removed():
    raw = json.dumps({"criteria": [row("a"), row("unknown")]})
    grade = {"criteria": [row("a")]}
    with pytest.raises(ValueError, match="every excluded ID"):
        verify_judgment_transform(raw, grade, {"a"}, TRIAL, {})
    check = verify_judgment_transform(
        raw, grade, {"a"}, TRIAL, {"excluded_from_normalized_grade": [{"id": "unknown"}]}
    )
    assert check["excluded_ids"] == ["unknown"]


def test_execution_override_requires_both_fact_and_provenance():
    original = row("correct_computation")
    raw = json.dumps({"criteria": [original]})
    wrong = {"criteria": [original]}
    with pytest.raises(ValueError, match="changed"):
        verify_judgment_transform(raw, wrong, {"correct_computation"}, TRIAL)
    fixed = {"criteria": [{**original, "pass": False}]}
    with pytest.raises(ValueError, match="provenance"):
        verify_judgment_transform(raw, fixed, {"correct_computation"}, TRIAL)
    fixed["criteria"][0].update(executionOverride=True, judgePass=True)
    result = verify_judgment_transform(raw, fixed, {"correct_computation"}, TRIAL)
    assert result["execution_changed_ids"] == ["correct_computation"]

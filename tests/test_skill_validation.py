"""Structural validation is not model-selection or behavioral evidence."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "skill_validator", Path(__file__).resolve().parents[1] / "scripts/validate_skill.py"
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def corpus() -> dict:
    return {
        "cases": [
            {
                "id": "case_one",
                "prompt": "Maintain the package.",
                "expected_output": {
                    "rubric_version": 1,
                    "criteria": [
                        {
                            "id": "first",
                            "description": "Pass only when scope is checked.",
                            "required": True,
                        },
                        {
                            "id": "second",
                            "description": "Pass only when proof is reported.",
                            "required": True,
                        },
                    ],
                },
            }
        ]
    }


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "example"
    (root / "evals").mkdir(parents=True)
    monkeypatch.setattr(validator, "SKILL", root)
    return root


def save(package: Path, data: object) -> None:
    (package / "evals/cases.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("data", [None, [], 1, "text", {"cases": [None]}, {"cases": [[]]}])
def test_malformed_documents_fail_with_contract_error(package: Path, data: object) -> None:
    save(package, data)
    with pytest.raises(ValueError):
        validator.validate_evals()


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", ""),
        ("id", []),
        ("id", " \t"),
        ("prompt", " \n"),
        ("prompt", ""),
        ("prompt", None),
        ("expected_output", []),
        ("expected_output", None),
    ],
)
def test_malformed_case_fields_fail_closed(package: Path, field: str, value: object) -> None:
    data = corpus()
    data["cases"][0][field] = value
    save(package, data)
    with pytest.raises(ValueError):
        validator.validate_evals()


@pytest.mark.parametrize(
    "criterion",
    [
        None,
        [],
        {"id": []},
        {
            "id": "bad",
            "description": "Pass only when ",
            "required": True,
        },
    ],
)
def test_malformed_criteria_fail_closed(package: Path, criterion: object) -> None:
    data = corpus()
    data["cases"][0]["expected_output"]["criteria"][0] = criterion
    save(package, data)
    with pytest.raises(ValueError):
        validator.validate_evals()


def test_duplicate_ids_fail_closed(package: Path) -> None:
    data = corpus()
    data["cases"].append(copy.deepcopy(data["cases"][0]))
    save(package, data)
    with pytest.raises(ValueError):
        validator.validate_evals()
    data = corpus()
    criteria = data["cases"][0]["expected_output"]["criteria"]
    criteria[1]["id"] = criteria[0]["id"]
    save(package, data)
    with pytest.raises(ValueError):
        validator.validate_evals()


def test_valid_corpus_is_unchanged(package: Path) -> None:
    save(package, corpus())
    before = (package / "evals/cases.json").read_bytes()
    validator.validate_evals()
    assert (package / "evals/cases.json").read_bytes() == before


@pytest.mark.parametrize("version", [True, False, 1.0, "1", None, 2])
def test_rubric_version_is_exact_integer(package: Path, version: object) -> None:
    data = corpus()
    data["cases"][0]["expected_output"]["rubric_version"] = version
    save(package, data)
    with pytest.raises(ValueError):
        validator.validate_evals()


@pytest.mark.parametrize("field,value", [("id", " \t"), ("description", "Pass only when \t")])
def test_whitespace_criterion_is_empty(package: Path, field: str, value: str) -> None:
    data = corpus()
    data["cases"][0]["expected_output"]["criteria"][0][field] = value
    save(package, data)
    with pytest.raises(ValueError):
        validator.validate_evals()


@pytest.mark.parametrize("second", ["missing", "malformed", "valid"])
def test_main_requires_both_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], second: str
) -> None:
    portable = tmp_path / "skills/compass"
    maintainer = tmp_path / ".pi/skills/compass-c-maintainer"
    for root in (portable, maintainer):
        if root == maintainer and second == "missing":
            continue
        (root / "evals").mkdir(parents=True)
        (root / "SKILL.md").write_text(
            f"---\nname: {root.name}\ndescription: Bounded synthetic skill.\n---\n# Example\n",
            encoding="utf-8",
        )
        save(root, [] if root == maintainer and second == "malformed" else corpus())
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "SKILL", portable)
    assert validator.main() == (0 if second == "valid" else 1)
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is (second == "valid")

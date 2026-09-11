#!/usr/bin/env python3
"""Convert retained Pi/GLM captures to COMPASS-C's existing paired-report contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

from compass_c import CompassError
from compass_c.cli import parse_json
from compass_c.evaluation import evaluate


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class _Pairs(list):
    """Distinguish JSON objects from arrays without losing duplicate keys."""


def _no_constant(value):
    raise ValueError(f"Non-finite JSON constant: {value}")


def _execution_override(criterion, trial):
    if criterion in {"no_notebook", "no_persistence"} and trial["notebookCreated"]:
        return False
    if criterion not in {"correct_computation", "computes_radius"}:
        return None
    field, expected = (
        ("pair_value", 20.25)
        if criterion == "correct_computation"
        else (
            "spectral_radius",
            0.5**0.5,
        )
    )
    for tool in trial["tools"]:
        if tool["name"] != "compass_calculate" or tool["isError"]:
            continue
        try:
            payload = parse_json(
                next(p["text"] for p in tool["result"]["content"] if p["type"] == "text")
            )
            value = payload["data"]["result"][field]
            if (
                payload["ok"] is True
                and type(value) in {int, float}
                and abs(value - expected) < 1e-8
            ):
                return True
        except (CompassError, KeyError, StopIteration, TypeError, OverflowError):
            continue
    return False


def verify_judgment_transform(raw, grade, expected_ids, trial, reconciliation=None):
    """Verify preservation/declared overrides, not the truth of the model's judgment."""
    parsed = json.loads(raw, object_pairs_hook=_Pairs, parse_constant=_no_constant)
    if type(parsed) is not _Pairs:
        raise ValueError("Raw judgment must be an object")
    keys = [key for key, _ in parsed]
    if any(keys.count(key) > 1 for key in keys if key != "criteria"):
        raise ValueError("Unaccounted duplicate root key")
    arrays = [value for key, value in parsed if key == "criteria"]
    if not arrays or any(type(value) is not list for value in arrays):
        raise ValueError("Raw criteria arrays are missing or malformed")
    raw_known, excluded = {}, []
    for array in arrays:
        for pairs in array:
            if type(pairs) is not _Pairs or len({key for key, _ in pairs}) != len(pairs):
                raise ValueError("Duplicate keys or malformed criterion object")
            item = dict(pairs)
            identifier = item.get("id")
            if type(identifier) is not str:
                raise ValueError("Missing or malformed raw criterion ID")
            if identifier not in expected_ids:
                excluded.append(identifier)
                continue
            if identifier in raw_known:
                raise ValueError("Repeated required judgment, possibly conflicting")
            if type(item.get("pass")) is not bool or type(item.get("evidence")) is not str:
                raise ValueError("Raw required judgment is incomplete")
            if not item["evidence"].strip():
                raise ValueError("Raw evidence is empty")
            item["evidence"].encode("utf-8")
            raw_known[identifier] = item
    if set(raw_known) != set(expected_ids):
        raise ValueError("Cannot invent missing required judgments")
    if len(arrays) != 1 or excluded:
        if reconciliation is None:
            raise ValueError("Format normalization requires a retained reconciliation")
        declared = reconciliation.get("excluded_from_normalized_grade", [])
        if isinstance(declared, dict):
            declared = [declared]
        if Counter(item["id"] for item in declared) != Counter(excluded):
            raise ValueError("Reconciliation does not account for every excluded ID")
    normalized = {item["id"]: item for item in grade["criteria"]}
    if len(normalized) != len(grade["criteria"]) or set(normalized) != set(expected_ids):
        raise ValueError("Normalized criterion set differs from the frozen rubric")
    overrides = []
    for identifier, original in raw_known.items():
        actual = normalized[identifier]
        observed = _execution_override(identifier, trial)
        expected_pass = original["pass"] if observed is None else observed
        if actual["pass"] is not expected_pass or actual["evidence"] != original["evidence"]:
            raise ValueError("Required judgment/evidence changed without a verified override")
        if "executionOverride" in actual or "judgePass" in actual:
            if (
                observed is None
                or actual.get("executionOverride") is not True
                or actual.get("judgePass") is not original["pass"]
            ):
                raise ValueError("Invalid execution-override provenance")
        elif expected_pass is not original["pass"]:
            raise ValueError("Changed judgment lacks execution-override provenance")
        if expected_pass is not original["pass"]:
            overrides.append(identifier)
    return {
        "criteria_arrays_checked": len(arrays),
        "excluded_ids": excluded,
        "required_judgments_checked": len(raw_known),
        "execution_changed_ids": overrides,
    }


def build_results(root, comparison, *, evidence_kind="host_observation"):
    protocol, corpus = load(root / "protocol.json"), load(root / "corpus.json")
    cases = {case["id"]: case for case in corpus["cases"]}
    phase = "aa" if comparison == "A/A" else "ab"
    results = {arm: [] for arm in ("baseline", "candidate")}
    captures = []
    digests = {}
    for item in protocol["schedule"]:
        if item["phase"] != phase:
            continue
        path, grade_path = root / f"{item['id']}.json", root / f"{item['id']}.grade.json"
        trial, grade = load(path), load(grade_path)
        transform_check = None
        if evidence_kind == "host_observation":
            raw_path = root / f"{item['id']}.judge.json"
            raw_record = load(raw_path)
            if raw_record.get("stopReason") != "stop":
                raise ValueError("Incomplete judge response cannot become a quality score")
            raw = raw_record["text"].strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            digests[raw_path.name] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            reference = grade.get("reconciliation", "")
            record = None
            try:
                parse_json(raw)  # Owner parser rejects duplicate keys, unlike JSON.parse.
            except CompassError as exc:
                if not reference:
                    raise ValueError(
                        f"Raw judgment requires reconciliation: {raw_path.name}"
                    ) from exc
            if reference:
                if Path(reference).name != reference:
                    raise ValueError("Reconciliation must stay inside the capture directory")
                reconciliation = root / reference
                record = load(reconciliation)
                if (
                    record.get("source") != raw_path.name
                    or record.get("kind") != "format_only_reconciliation_not_rescoring"
                    or type(record.get("new_model_calls")) is not int
                    or record.get("new_model_calls") != 0
                    or record.get("raw_response_preserved") is not True
                ):
                    raise ValueError("Invalid format-reconciliation record")
                digests[reference] = hashlib.sha256(reconciliation.read_bytes()).hexdigest()
            expected = {c["id"] for c in cases[item["caseId"]]["expected_output"]["criteria"]}
            transform_check = verify_judgment_transform(raw, grade, expected, trial, record)
        if trial["status"] not in {"executed", "bounded_failure"}:
            raise ValueError("Indeterminate captures cannot become a paired report")
        scores = {c["id"]: c["pass"] for c in grade["criteria"]}
        if len(scores) != len(grade["criteria"]):
            raise ValueError("Duplicate graded criterion")
        reads = [
            t["arguments"]["path"]
            for t in trial["tools"]
            if t["name"] == "read" and not t["isError"]
        ]
        selected = any(path.endswith("/SKILL.md") for path in reads)
        results[item["arm"]].append(
            {
                "case_id": item["caseId"],
                "compass_selected": selected,
                # Loading a resource does not by itself prove primary workflow ownership.
                "primary_skill": None,
                "scores": scores,
                "response_ref": os.path.relpath(path, Path(__file__).resolve().parents[1]),
            }
        )
        successes = []
        for tool in trial["tools"]:
            if tool["name"] == "read" or tool["isError"]:
                continue
            try:
                payload = json.loads(
                    next(p["text"] for p in tool["result"]["content"] if p["type"] == "text")
                )
                if payload["ok"]:
                    successes.append(tool["name"])
            except (KeyError, ValueError, StopIteration):
                continue
        captures.append(
            {
                "id": item["id"],
                "arm": item["arm"],
                "case_id": item["caseId"],
                "status": trial["status"],
                "grade_status": grade.get("status", "synthetic_fixture"),
                "format_reconciliation": grade.get("reconciliation"),
                "judgment_transform_check": transform_check,
                "skill_read": selected,
                "reference_read": any("/references/" in p for p in reads),
                "evaluation_material_reads": [p for p in reads if "/evals/" in p],
                "notebook_created": trial["notebookCreated"],
                "successful_mcp_tools": successes,
                "duration_ms": trial["durationMs"],
            }
        )
        for artifact in (path, grade_path):
            digests[artifact.name] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    revision = "compass-0.6.0:" + protocol["skillTreeSha256"]
    paired = {
        "schema_version": 1,
        "comparison": comparison,
        "evidence_kind": evidence_kind,
        "corpus_sha256": fingerprint(corpus),
        "host": {
            "name": "Pi SDK " + protocol["piVersion"],
            "model": "zai/glm-5.3-flash",
            "configuration": "protocol.json; native skill discovery, bounded reads, live MCP; "
            "temperature0.7, thinking off, max4096 tokens/16 requests, "
            "two concurrent fresh sessions; no persistent host settings",
        },
        "grader": "Fresh same-model contexts; frozen criteria; no arm label; execution overrides. "
        "Advisory, not independent expert evidence. Raw judgments and any format-only "
        "reconciliation records retained; no trial resampling. "
        "Routing means observed SKILL.md acquisition; primary owner unmeasured.",
        "baseline": {
            "revision": revision if phase == "aa" else "no-skill-discovery",
            "results": results["baseline"],
        },
        "candidate": {"revision": revision, "results": results["candidate"]},
    }
    report = evaluate(
        corpus, paired
    )  # Source-owned validation and statistics, not a parallel engine.
    return (
        paired,
        report,
        {
            "captures": captures,
            "artifact_sha256": digests,
            "successful_tool_counts": dict(
                Counter(t for c in captures for t in c["successful_mcp_tools"])
            ),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    for comparison in ("A/A", "A/B"):
        paired, report, captures = build_results(args.run, comparison)
        prefix = comparison.replace("/", "").lower()
        for suffix, value in (
            ("results", paired),
            ("report", report),
            ("capture-metrics", captures),
        ):
            with (args.run / f"{prefix}-{suffix}.json").open("x", encoding="utf-8") as output:
                json.dump(value, output, indent=2, ensure_ascii=False, allow_nan=False)
                output.write("\n")
        print(json.dumps({"comparison": comparison, "report": f"{prefix}-report.json"}))


if __name__ == "__main__":
    main()

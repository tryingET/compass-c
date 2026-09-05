from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from rocs_cli.capabilities import CAPABILITY_NAMES, CLASS_REQUIREMENTS
from rocs_cli.fcos_gate import (
    FCOS_CI_WRAPPER_CANDIDATES,
    FCOS_CI_WRAPPER_TEMPLATE_CANDIDATES,
    FCOS_GATE_HOOK_CANDIDATES,
    FCOS_GATE_HOOK_PATH,
    FCOS_GATE_HOOK_TEMPLATE_CANDIDATES,
    LEGACY_FCOS_GATE_CANDIDATES,
    hook_contract_evidence,
    wrapper_workspace_contract_evidence,
)
from rocs_cli.fleet_detection import (
    LOCATOR_RE,
    MANIFEST_CANDIDATES,
    _blocked_hits,
    _detect_capabilities,
    _hook_contract_status,
    _manifest_contract_status,
    _probe_paths,
    _safe_bool,
    _valid_hits,
    _wrapper_workspace_contract,
)
from rocs_cli.fleet_policy import (
    CAPABILITY_KEYS,
    PolicyError,
    _load_policy,
    _require_list,
    _require_mapping,
    _validate_policy,
)
from rocs_cli.fleet_preflight import (
    FileProbe,
    FleetPreflightError,
    normalize_policy_repo_path,
    probe_managed_candidates,
    read_utf8_text,
)
from rocs_cli.managed_surface import strip_hash_comments, yaml_scalar_strings
from rocs_cli.vendored import verify_vendored_hashes


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_VIOLATIONS = 2


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit FCOS fleet policy capabilities and emit deterministic scorecards."
    )
    parser.add_argument("--workspace-root", required=True, help="Workspace root containing local repos")
    parser.add_argument("--policy", required=True, help="Path to fleet-state.yaml")
    parser.add_argument(
        "--json",
        nargs="?",
        const="-",
        default=None,
        metavar="PATH",
        help="Emit JSON scorecard (default stdout when PATH omitted)",
    )
    parser.add_argument(
        "--markdown",
        nargs="?",
        const="-",
        default=None,
        metavar="PATH",
        help="Emit Markdown scorecard (default stdout when PATH omitted)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Always exit 0 even when capability violations are found",
    )
    return parser.parse_args(argv)



def _sort_caps(caps: dict[str, Any]) -> dict[str, Any]:
    return {k: caps.get(k) for k in CAPABILITY_KEYS}


def _build_scorecard(
    policy: dict[str, Any], *, workspace_root: Path, policy_path: Path, report_only: bool
) -> dict[str, Any]:
    repo_classes = policy["repo_classes"]
    fleet_entries = policy["fleet"]["repos"]
    kill_switch_mode = policy.get("kill_switch", {}).get("fcos_enforcement", {}).get("mode", "unknown")

    repo_rows: list[dict[str, Any]] = []
    total_require_violations = 0
    total_decl_drifts = 0

    for entry_any in sorted(fleet_entries, key=lambda x: str(x.get("path", ""))):
        entry = dict(entry_any)
        policy_repo_path = str(entry.get("path", ""))
        resolved, path_issue = normalize_policy_repo_path(workspace_root, policy_repo_path)
        exists = path_issue is None and resolved.is_dir()

        repo_class = str(entry.get("class"))
        expected_caps = _sort_caps(repo_classes[repo_class]["required_capabilities"])
        declared_caps = _sort_caps(entry.get("capabilities", {}))

        if exists:
            observed_caps, evidence = _detect_capabilities(resolved)
        else:
            observed_caps = {k: False for k in CAPABILITY_KEYS}
            if path_issue is not None:
                evidence = {
                    "path_boundary": {
                        "resolved": str(resolved),
                        "reason": path_issue,
                    }
                }
            else:
                evidence = {
                    "missing_path": {
                        "resolved": str(resolved),
                    }
                }

        requirement_violations: list[str] = []
        for key in CAPABILITY_KEYS:
            if expected_caps.get(key) is True and observed_caps.get(key) is not True:
                requirement_violations.append(key)

        declaration_drifts: list[str] = []
        for key in CAPABILITY_KEYS:
            declared_bool = _safe_bool(declared_caps.get(key))
            if declared_bool is None:
                continue
            if declared_bool != observed_caps.get(key):
                declaration_drifts.append(key)

        total_require_violations += len(requirement_violations)
        total_decl_drifts += len(declaration_drifts)

        row = {
            "path": policy_repo_path,
            "resolved_path": str(resolved),
            "scope": entry.get("scope"),
            "class": repo_class,
            "state": entry.get("state"),
            "owner": entry.get("owner"),
            "exists": exists,
            "expected_capabilities": expected_caps,
            "declared_capabilities": declared_caps,
            "observed_capabilities": observed_caps,
            "requirement_violations": requirement_violations,
            "declaration_drifts": declaration_drifts,
            "evidence": evidence,
        }
        repo_rows.append(row)

    requirement_violation_entries = [r for r in repo_rows if r["requirement_violations"]]
    declaration_drift_entries = [r for r in repo_rows if r["declaration_drifts"]]

    exit_code = EXIT_OK if total_require_violations == 0 and total_decl_drifts == 0 else EXIT_VIOLATIONS
    if report_only:
        exit_code = EXIT_OK

    summary = {
        "total_entries": len(repo_rows),
        "existing_entries": sum(1 for r in repo_rows if r["exists"]),
        "missing_entries": sum(1 for r in repo_rows if not r["exists"]),
        "requirement_violation_entries": len(requirement_violation_entries),
        "requirement_violations": total_require_violations,
        "declaration_drift_entries": len(declaration_drift_entries),
        "declaration_drifts": total_decl_drifts,
        "status": "fail" if total_require_violations else "action_required" if total_decl_drifts else "pass",
    }

    scorecard = {
        "schema_version": 2,
        "workspace_root": str(workspace_root),
        "policy": str(policy_path),
        "kill_switch_mode": kill_switch_mode,
        "report_only": report_only,
        "summary": summary,
        "repos": repo_rows,
        "violations": {
            "required_capabilities": [
                {
                    "path": r["path"],
                    "class": r["class"],
                    "missing": r["requirement_violations"],
                }
                for r in requirement_violation_entries
            ],
            "declaration_drifts": [
                {
                    "path": r["path"],
                    "class": r["class"],
                    "drifts": r["declaration_drifts"],
                }
                for r in declaration_drift_entries
            ],
        },
        "exit_code": exit_code,
        "exit_codes": {
            "ok": EXIT_OK,
            "error": EXIT_ERROR,
            "violations": EXIT_VIOLATIONS,
        },
    }
    canonical = json.dumps(scorecard, sort_keys=True, separators=(",", ":")).encode("utf-8")
    scorecard["integrity"] = {
        "algorithm": "sha256",
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "evidence_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    return scorecard


def _yn(value: bool) -> str:
    return "yes" if value else "no"


def _render_markdown(scorecard: dict[str, Any]) -> str:
    s = scorecard["summary"]
    lines: list[str] = []
    lines.append("# FCOS Fleet Audit Scorecard")
    lines.append("")
    lines.append(f"- workspace_root: `{scorecard['workspace_root']}`")
    lines.append(f"- policy: `{scorecard['policy']}`")
    lines.append(f"- kill_switch_mode: `{scorecard['kill_switch_mode']}`")
    lines.append(f"- report_only: `{str(scorecard['report_only']).lower()}`")
    lines.append(f"- status: `{s['status']}`")
    lines.append(f"- suggested_exit_code: `{scorecard['exit_code']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|---|---:|")
    lines.append(f"| total_entries | {s['total_entries']} |")
    lines.append(f"| existing_entries | {s['existing_entries']} |")
    lines.append(f"| missing_entries | {s['missing_entries']} |")
    lines.append(f"| requirement_violation_entries | {s['requirement_violation_entries']} |")
    lines.append(f"| requirement_violations | {s['requirement_violations']} |")
    lines.append(f"| declaration_drift_entries | {s['declaration_drift_entries']} |")
    lines.append(f"| declaration_drifts | {s['declaration_drifts']} |")
    lines.append("")

    req_viol = scorecard["violations"]["required_capabilities"]
    lines.append("## Required Capability Violations")
    lines.append("")
    if not req_viol:
        lines.append("none")
        lines.append("")
    else:
        lines.append("| path | class | missing_required_capabilities |")
        lines.append("|---|---|---|")
        for row in req_viol:
            lines.append(f"| `{row['path']}` | `{row['class']}` | `{', '.join(row['missing'])}` |")
        lines.append("")

    lines.append("## Repo Results")
    lines.append("")
    lines.append(
        "| path | class | exists | rocs_cli_vendored | ontology_manifest | rocs_ci_gate | required_missing | declaration_drifts |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in scorecard["repos"]:
        obs = row["observed_capabilities"]
        missing = ", ".join(row["requirement_violations"]) or "-"
        drifts = ", ".join(row["declaration_drifts"]) or "-"
        lines.append(
            "| `{path}` | `{cls}` | {exists} | {vendored} | {manifest} | {ci} | `{missing}` | `{drifts}` |".format(
                path=row["path"],
                cls=row["class"],
                exists=_yn(bool(row["exists"])),
                vendored=_yn(bool(obs.get("rocs_cli_vendored"))),
                manifest=_yn(bool(obs.get("ontology_manifest"))),
                ci=_yn(bool(obs.get("rocs_ci_gate"))),
                missing=missing,
                drifts=drifts,
            )
        )

    return "\n".join(lines).rstrip() + "\n"


def _write_output(dest: str, payload: str) -> None:
    if dest == "-":
        sys.stdout.write(payload)
        return
    out = Path(dest).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, "utf-8")


def observe(workspace_root: Path, policy_path: Path, *, report_only: bool = False) -> tuple[dict[str, Any], int]:
    """Observe fleet state without mutation."""
    workspace_root, policy_path = workspace_root.resolve(), policy_path.resolve()
    if not workspace_root.is_dir():
        raise PolicyError(f"workspace root not found: {workspace_root}")
    policy = _load_policy(policy_path)
    _validate_policy(policy, workspace_root=workspace_root)
    scorecard = _build_scorecard(
        policy, workspace_root=workspace_root, policy_path=policy_path, report_only=report_only
    )
    scorecard["operation"] = "observe"
    return scorecard, int(scorecard["exit_code"])


def plan(workspace_root: Path, policy_path: Path) -> tuple[dict[str, Any], int]:
    """Produce deterministic convergence actions from fresh observations."""
    observed, _ = observe(workspace_root, policy_path, report_only=True)
    actions = [
        {"action": "converge", "path": row["path"], "class": row["class"], "missing": row["requirement_violations"]}
        for row in observed["repos"]
        if row["requirement_violations"]
    ]
    actions.extend(
        {"action": "manual-governance-followup", "path": row["path"], "class": row["class"],
         "declaration_drifts": row["declaration_drifts"]}
        for row in observed["repos"] if row["declaration_drifts"]
    )
    actions.sort(key=lambda action: (action["path"], action["action"]))
    payload = {
        "schema_version": 1,
        "operation": "plan",
        "workspace_root": str(workspace_root.resolve()),
        "policy": str(policy_path.resolve()),
        "observation_integrity": observed["integrity"],
        "actions": actions,
    }
    return payload, EXIT_VIOLATIONS if actions else EXIT_OK


def apply(workspace_root: Path, policy_path: Path, *, dry_run: bool = False) -> tuple[dict[str, Any], int]:
    """Apply only bootstrap-managed actions from a freshly recomputed plan."""
    from rocs_cli.wave1 import bootstrap

    payload, _ = plan(workspace_root, policy_path)
    results = []
    failed = False
    action_required = False
    for action in payload["actions"]:
        target = workspace_root.resolve() / action["path"]
        if action["action"] != "converge":
            action_required = True
            results.append({"target": str(target), "ok": False, "blocked": True,
                            "action": action["action"], "reason": "governance declaration drift requires owner follow-up"})
            continue
        try:
            results.append(bootstrap(target, action["class"], dry_run=dry_run, converge=True))
        except (OSError, ValueError, RuntimeError) as exc:
            failed = True
            results.append({"target": str(target), "ok": False, "error": str(exc)})
    code = EXIT_ERROR if failed else EXIT_VIOLATIONS if action_required else EXIT_OK
    return {**payload, "operation": "apply", "dry_run": dry_run, "results": results}, code


def run(workspace_root: Path, policy_path: Path, *, mode: str = "apply") -> tuple[dict[str, Any], int]:
    """Execute the closed nightly loop and include final observation evidence."""
    if mode == "audit-only":
        applied, apply_code = ({"operation": "apply", "results": []}, EXIT_OK)
    else:
        applied, apply_code = apply(workspace_root, policy_path, dry_run=mode == "patch")
    final, final_code = observe(workspace_root, policy_path)
    payload = {"schema_version": 1, "operation": "run", "mode": mode, "apply": applied, "final": final}
    return payload, apply_code or final_code


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    policy_path = Path(args.policy).expanduser().resolve()

    if not workspace_root.is_dir():
        print(f"error: workspace root not found: {workspace_root}", file=sys.stderr)
        return EXIT_ERROR

    try:
        policy = _load_policy(policy_path)
        _validate_policy(policy, workspace_root=workspace_root)
        scorecard = _build_scorecard(
            policy,
            workspace_root=workspace_root,
            policy_path=policy_path,
            report_only=bool(args.report_only),
        )
    except (PolicyError, FleetPreflightError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    json_payload = json.dumps(scorecard, indent=2, sort_keys=True) + "\n"
    md_payload = _render_markdown(scorecard)

    json_dest = args.json
    md_dest = args.markdown

    if json_dest is None and md_dest is None:
        json_dest = "-"

    if json_dest == "-" and md_dest == "-":
        sys.stdout.write(json_payload)
        sys.stdout.write("\n---\n\n")
        sys.stdout.write(md_payload)
    else:
        if json_dest is not None:
            _write_output(json_dest, json_payload)
        if md_dest is not None:
            _write_output(md_dest, md_payload)

    return int(scorecard["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

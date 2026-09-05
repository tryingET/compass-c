from __future__ import annotations

import argparse
import json
import shutil
from typing import cast

from rocs_cli import __version__
from rocs_cli.authority import effective_workspace_ref_mode
from rocs_cli.cli_support import (
    _clear_build_artifacts,
    _ensure_dist_dir,
    _finding_summary,
    _findings_to_json,
    _load_view,
    _print_findings,
    _write_authority_receipt_if_possible,
    _write_resolve_artifact,
    get_console,
)
from rocs_cli.errors import RocsCliError
from rocs_cli.id_index import build_id_index
from rocs_cli.layers import dist_dir, repo_root as _repo_root
from rocs_cli.managed_surface import ensure_managed_output_file
from rocs_cli.rules import Finding
from rocs_cli.rulesets import behavior_for_ruleset, effective_ruleset
from rocs_cli.validate import validate_repo_structure
from rocs_cli.validation_service import _schema_validation_result

def cmd_resolve(args: argparse.Namespace) -> int:
    view = _load_view(args, load_docs=False)
    repo = view.repo
    profile_name = (
        view.meta.get("profile") if isinstance(view.meta, dict) and isinstance(view.meta.get("profile"), str) else None
    )
    resolution_notes = view.meta.get("resolution_notes") if isinstance(view.meta, dict) else None
    layer_entries: list[dict[str, object]] = []
    for layer_spec in view.layers:
        entry: dict[str, object] = {
            "name": layer_spec.name,
            "origin": layer_spec.origin,
            "src_root": str(layer_spec.src_root),
            "kind": layer_spec.kind,
            "source": layer_spec.source,
            "source_contract": layer_spec.source_contract,
        }
        if args.show_resolve_details:
            entry["details"] = (resolution_notes or {}).get(layer_spec.name)
        layer_entries.append(entry)
    for layer_entry in layer_entries:
        if layer_entry.get("details") is None:
            layer_entry.pop("details", None)

    payload: dict[str, object] = {"repo": str(repo), "profile": profile_name, "layers": layer_entries}
    if args.write_dist:
        _write_resolve_artifact(repo, layers=view.layers, profile=profile_name)
    if args.json:
        get_console().print_json(json.dumps(payload))
    else:
        get_console().print(f"repo: {repo}")
        get_console().print(f"profile: {profile_name}")
        for layer_entry in layer_entries:
            name = str(layer_entry.get("name") or "")
            origin = str(layer_entry.get("origin") or "")
            if args.show_resolve_sources or args.show_resolve_details:
                source = str(layer_entry.get("source") or "")
                extra = f"source={source}"
                details = layer_entry.get("details")
                if args.show_resolve_details and isinstance(details, dict):
                    details_map = cast(dict[str, object], details)
                    ws_obj = details_map.get("workspace")
                    if isinstance(ws_obj, dict):
                        ws = cast(dict[str, object], ws_obj)
                        if ws.get("present"):
                            if not ws.get("used") and ws.get("reason"):
                                extra += f"; workspace={ws.get('reason')}"
                get_console().print(f"- layer {name}: {origin} ({extra})")
            else:
                get_console().print(f"- layer {name}: {origin}")
    return 0

def cmd_summary(args: argparse.Namespace) -> int:
    view = _load_view(args)
    repo = view.repo
    profile_name = (
        view.meta.get("profile") if isinstance(view.meta, dict) and isinstance(view.meta.get("profile"), str) else None
    )
    resolution_notes = view.meta.get("resolution_notes") if isinstance(view.meta, dict) else None
    layer_entries: list[dict[str, object]] = []
    for layer_spec in view.layers:
        entry: dict[str, object] = {
            "name": layer_spec.name,
            "origin": layer_spec.origin,
            "src_root": str(layer_spec.src_root),
            "kind": layer_spec.kind,
            "source": layer_spec.source,
            "source_contract": layer_spec.source_contract,
        }
        if args.show_resolve_details:
            entry["details"] = (resolution_notes or {}).get(layer_spec.name)
        layer_entries.append(entry)
    for layer_entry in layer_entries:
        if layer_entry.get("details") is None:
            layer_entry.pop("details", None)
    payload: dict[str, object] = {
        "repo": str(repo),
        "profile": profile_name,
        "layers": layer_entries,
        "counts": {"concepts": len(view.concepts), "relations": len(view.relations)},
    }
    conformance = view.source_conformance("summary", complete_success=True)
    if conformance is not None:
        payload["source_contract_conformance"] = conformance
    if not args.json:
        get_console().print(f"repo: {repo}")
        get_console().print(f"profile: {profile_name}")
        get_console().print(f"counts: concepts={len(view.concepts)} relations={len(view.relations)}")
        for layer_entry in layer_entries:
            name = str(layer_entry.get("name") or "")
            origin = str(layer_entry.get("origin") or "")
            if args.show_resolve_sources or args.show_resolve_details:
                source = str(layer_entry.get("source") or "")
                extra = f"source={source}"
                details = layer_entry.get("details")
                if args.show_resolve_details and isinstance(details, dict):
                    details_map = cast(dict[str, object], details)
                    ws_obj = details_map.get("workspace")
                    if isinstance(ws_obj, dict):
                        ws = cast(dict[str, object], ws_obj)
                        if ws.get("present"):
                            if not ws.get("used") and ws.get("reason"):
                                extra += f"; workspace={ws.get('reason')}"
                get_console().print(f"- layer {name}: {origin} ({extra})")
            else:
                get_console().print(f"- layer {name}: {origin}")
    else:
        get_console().print_json(json.dumps(payload))
    return 0

def cmd_validate(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo)
    ws_mode = effective_workspace_ref_mode(getattr(args, "workspace_ref_mode", None))
    findings: list[Finding] = []
    findings.extend(validate_repo_structure(repo))
    if findings:
        _write_authority_receipt_if_possible(
            repo,
            command="validate",
            ok=False,
            profile=getattr(args, "profile", None),
            resolve_refs_requested=bool(args.resolve_refs),
            workspace_ref_mode=ws_mode,
            layers=[],
            result=_finding_summary(findings),
        )
        if args.json:
            get_console().print_json(
                json.dumps(
                    {"ok": False, "findings": _findings_to_json(findings), "budget": {"budget": None, "units": None}}
                )
            )
        else:
            get_console().print("[red]rocs validate: FAIL[/red]")
            _print_findings(findings)
        return 1
    try:
        view = _load_view(args)
    except RocsCliError as e:
        _write_authority_receipt_if_possible(
            repo,
            command="validate",
            ok=False,
            profile=getattr(args, "profile", None),
            resolve_refs_requested=bool(args.resolve_refs),
            workspace_ref_mode=ws_mode,
            layers=[],
            error=e,
        )
        raise
    profile_name = (
        view.meta.get("profile") if isinstance(view.meta, dict) and isinstance(view.meta.get("profile"), str) else None
    )
    profile_def = view.meta.get("profile_def") if isinstance(view.meta, dict) else None
    ruleset_name = effective_ruleset(cli_ruleset=getattr(args, "ruleset", None), profile_def=profile_def)
    ruleset_behavior = behavior_for_ruleset(ruleset_name)
    strict_placeholders = bool(args.strict_placeholders or ruleset_behavior.strict_placeholders)

    findings, budget_payload = _schema_validation_result(
        view,
        strict_placeholders=strict_placeholders,
        validate_deps=bool(args.validate_deps),
    )

    ok = not findings
    conformance = view.source_conformance("validate", complete_success=ok)
    _write_authority_receipt_if_possible(
        repo,
        command="validate",
        ok=ok,
        profile=profile_name,
        resolve_refs_requested=bool(args.resolve_refs),
        workspace_ref_mode=ws_mode,
        layers=view.layers,
        result=_finding_summary(findings),
        source_contract_conformance=conformance,
    )
    if findings:
        if args.json:
            get_console().print_json(
                json.dumps({"ok": False, "findings": _findings_to_json(findings), "budget": budget_payload})
            )
        else:
            get_console().print("[red]rocs validate: FAIL[/red]")
            _print_findings(findings)
        return 1

    if args.json:
        success_payload: dict[str, object] = {"ok": True, "findings": [], "budget": budget_payload}
        if conformance is not None:
            success_payload["source_contract_conformance"] = conformance
        get_console().print_json(json.dumps(success_payload))
    else:
        get_console().print("[green]rocs validate: OK[/green]")
    return 0

def cmd_build(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo)
    ws_mode = effective_workspace_ref_mode(getattr(args, "workspace_ref_mode", None))
    dist = dist_dir(repo)
    _ensure_dist_dir(repo, label="build output dir")
    if args.clean and dist.exists():
        shutil.rmtree(dist)
    _ensure_dist_dir(repo, label="build output dir")
    _clear_build_artifacts(repo)
    try:
        view = _load_view(args)
    except RocsCliError as e:
        _write_authority_receipt_if_possible(
            repo,
            command="build",
            ok=False,
            profile=getattr(args, "profile", None),
            resolve_refs_requested=bool(args.resolve_refs),
            workspace_ref_mode=ws_mode,
            layers=[],
            error=e,
        )
        raise
    profile_name = (
        view.meta.get("profile") if isinstance(view.meta, dict) and isinstance(view.meta.get("profile"), str) else None
    )
    profile_def = view.meta.get("profile_def") if isinstance(view.meta, dict) else None
    ruleset_name = effective_ruleset(cli_ruleset=None, profile_def=profile_def)
    strict_placeholders = behavior_for_ruleset(ruleset_name).strict_placeholders
    findings, _budget_payload = _schema_validation_result(
        view,
        strict_placeholders=strict_placeholders,
        validate_deps=True,
    )
    if findings:
        _write_authority_receipt_if_possible(
            repo,
            command="build",
            ok=False,
            profile=profile_name,
            resolve_refs_requested=bool(args.resolve_refs),
            workspace_ref_mode=ws_mode,
            layers=view.layers,
            result=_finding_summary(findings),
        )
        if args.json:
            get_console().print_json(json.dumps({"ok": False, "findings": _findings_to_json(findings)}))
        else:
            get_console().print("[red]rocs build: FAIL[/red]")
            _print_findings(findings)
        return 1

    resolve_out = _write_resolve_artifact(repo, layers=view.layers, profile=profile_name)
    payload = {
        "schema_version": 1,
        "version": __version__,
        "repo": str(repo),
        "profile": profile_name,
        "layers": [{"name": layer_spec.name, "origin": layer_spec.origin} for layer_spec in view.layers],
        "counts": {"concepts": len(view.concepts), "relations": len(view.relations)},
        "concept_ids": sorted(view.concepts.keys()),
        "relation_ids": sorted(view.relations.keys()),
    }
    summary_out = ensure_managed_output_file(repo, dist / "summary.json", label="build summary artifact")
    summary_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    id_index_out = ensure_managed_output_file(repo, dist / "id_index.json", label="build id-index artifact")
    id_index_out.write_text(
        json.dumps(build_id_index(concepts=view.concepts, relations=view.relations), indent=2, sort_keys=True) + "\n",
        "utf-8",
    )
    conformance = view.source_conformance("build", complete_success=True)
    authority_receipt_out = _write_authority_receipt_if_possible(
        repo,
        command="build",
        ok=True,
        profile=profile_name,
        resolve_refs_requested=bool(args.resolve_refs),
        workspace_ref_mode=ws_mode,
        layers=view.layers,
        source_contract_conformance=conformance,
    )
    if args.json:
        files = {
            "resolve": str(resolve_out),
            "summary": str(summary_out),
            "id_index": str(id_index_out),
        }
        if authority_receipt_out is not None:
            files["authority_receipt"] = str(authority_receipt_out["aggregate"])
            files["authority_receipt_command"] = str(authority_receipt_out["command"])
        get_console().print_json(
            json.dumps(
                {
                    "repo": str(repo),
                    "profile": profile_name,
                    "dist": {
                        "dir": str(dist),
                        "files": files,
                    },
                    "counts": payload.get("counts"),
                    **({"source_contract_conformance": conformance} if conformance is not None else {}),
                }
            )
        )
    else:
        get_console().print(f"[green]wrote[/green] {summary_out}")
        get_console().print(f"[green]wrote[/green] {id_index_out}")
        if authority_receipt_out is not None:
            get_console().print(f"[green]wrote[/green] {authority_receipt_out['aggregate']}")
            get_console().print(f"[green]wrote[/green] {authority_receipt_out['command']}")
    return 0

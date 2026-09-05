from __future__ import annotations

import re
from pathlib import Path
from typing import Any

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
from rocs_cli.fleet_policy import CAPABILITY_KEYS
from rocs_cli.fleet_preflight import FileProbe, probe_managed_candidates
from rocs_cli.managed_surface import strip_hash_comments, yaml_scalar_strings
from rocs_cli.vendored import verify_vendored_hashes


MANIFEST_CANDIDATES: tuple[str, ...] = (
    "ontology/manifest.yaml",
    "ontology/manifest.yml",
    "ontology/manifest.yaml.j2",
    "ontology/manifest.yml.j2",
    "ontology/manifest.yaml.jinja",
    "ontology/manifest.yml.jinja",
    "manifest.yaml",
    "manifest.yml",
    "manifest.yaml.j2",
    "manifest.yml.j2",
    "manifest.yaml.jinja",
    "manifest.yml.jinja",
)

LOCATOR_RE = re.compile(r"<(?P<kind>repo|gitlab):[^>]+>")


def _probe_paths(base: Path, candidates: tuple[str, ...], *, label: str, load_text: bool = False) -> list[FileProbe]:
    return probe_managed_candidates(base, candidates, label=label, load_text=load_text)


def _valid_hits(probes: list[FileProbe]) -> list[str]:
    return [probe.relpath for probe in probes if probe.valid]


def _blocked_hits(probes: list[FileProbe]) -> list[dict[str, str]]:
    return [
        {"path": probe.relpath, "reason": str(probe.blocker or "unknown")}
        for probe in probes
        if probe.present and not probe.valid
    ]


def _manifest_contract_status(manifest_probes: list[FileProbe]) -> tuple[bool, dict[str, Any], bool]:
    valid_probes = [probe for probe in manifest_probes if probe.valid]
    blocked_hits = _blocked_hits(manifest_probes)
    if not valid_probes:
        evidence: dict[str, Any] = {"primary_hit": None, "locator_kind": "missing", "locators": []}
        if blocked_hits:
            evidence.update(
                {
                    "primary_hit": blocked_hits[0]["path"],
                    "locator_kind": "invalid",
                    "parse_error": blocked_hits[0]["reason"],
                    "blocked_hits": blocked_hits,
                }
            )
        return False, evidence, False

    primary_probe = valid_probes[0]
    text = primary_probe.text or ""
    scalar_strings = yaml_scalar_strings(text)
    if scalar_strings is not None:
        locator_source = "yaml_scalars"
        locator_chunks = scalar_strings
    else:
        locator_source = "comment_stripped_text"
        locator_chunks = [strip_hash_comments(text)]

    locators = [
        {"kind": match.group("kind"), "value": match.group(0)}
        for chunk in locator_chunks
        for match in LOCATOR_RE.finditer(chunk)
    ]
    repo_locators = [entry["value"] for entry in locators if entry["kind"] == "repo"]
    gitlab_locators = [entry["value"] for entry in locators if entry["kind"] == "gitlab"]

    if gitlab_locators and repo_locators:
        locator_kind = "mixed"
    elif gitlab_locators:
        locator_kind = "gitlab"
    elif repo_locators:
        locator_kind = "repo"
    else:
        locator_kind = "none"

    contract_ok = not gitlab_locators
    evidence = {
        "primary_hit": primary_probe.relpath,
        "locator_kind": locator_kind,
        "locator_source": locator_source,
        "locators": locators,
        "requires_workspace_contract": bool(repo_locators),
    }
    if blocked_hits:
        evidence["blocked_hits"] = blocked_hits
    if gitlab_locators:
        evidence["contract_reason"] = "legacy_gitlab_locators"

    return contract_ok, evidence, bool(repo_locators)


def _wrapper_workspace_contract(wrapper_probes: list[FileProbe]) -> tuple[bool, dict[str, Any]]:
    valid_probes = [probe for probe in wrapper_probes if probe.valid]
    checked: list[str] = [probe.relpath for probe in valid_probes]
    workspace_root_present = False
    workspace_ref_mode_present = False
    wrapper_contract_lines: list[dict[str, Any]] = []

    for probe in valid_probes:
        contract = wrapper_workspace_contract_evidence(probe.text or "")
        wrapper_contract_lines.append({"path": probe.relpath, "lines": contract["lines"]})
        workspace_root_present = workspace_root_present or bool(contract["workspace_root_present"])
        workspace_ref_mode_present = workspace_ref_mode_present or bool(contract["workspace_ref_mode_present"])

    ok = workspace_root_present and workspace_ref_mode_present
    evidence: dict[str, Any] = {
        "wrapper_workspace_checked": checked,
        "wrapper_contract_lines": wrapper_contract_lines,
        "workspace_root_present": workspace_root_present,
        "workspace_ref_mode_present": workspace_ref_mode_present,
    }
    blocked_hits = _blocked_hits(wrapper_probes)
    if blocked_hits:
        evidence["wrapper_workspace_blocked_hits"] = blocked_hits
    return ok, evidence


def _hook_contract_status(base: Path, *, requires_workspace_contract: bool) -> tuple[bool, dict[str, Any]]:
    hook_probes = _probe_paths(base, FCOS_GATE_HOOK_CANDIDATES, label="ROCS gate hook", load_text=True)
    hook_template_probes = _probe_paths(base, FCOS_GATE_HOOK_TEMPLATE_CANDIDATES, label="ROCS gate hook template")
    wrapper_probes = _probe_paths(base, FCOS_CI_WRAPPER_CANDIDATES, label="ROCS CI wrapper", load_text=True)
    wrapper_template_probes = _probe_paths(base, FCOS_CI_WRAPPER_TEMPLATE_CANDIDATES, label="ROCS CI wrapper template")
    legacy_gate_probes = _probe_paths(base, LEGACY_FCOS_GATE_CANDIDATES, label="legacy ROCS gate")
    wrapper_call_present = False
    profile_contract_present = False
    hook_contract_checked: list[str] = []
    hook_contexts_checked: list[dict[str, Any]] = []
    hook_exec_checked: dict[str, bool] = {}
    hook_exec_required = False
    hook_exec_present = False

    valid_hook_probes = [probe for probe in hook_probes if probe.valid]
    for probe in valid_hook_probes:
        hook_contract_checked.append(probe.relpath)

        exec_required = probe.relpath == FCOS_GATE_HOOK_PATH
        is_executable = True
        if exec_required:
            hook_exec_required = True
            try:
                is_executable = bool(probe.path.stat().st_mode & 0o111)
            except OSError:
                is_executable = False
            hook_exec_checked[probe.relpath] = is_executable
            if is_executable:
                hook_exec_present = True

        contract = hook_contract_evidence(probe.text or "")
        hook_contexts_checked.append({"path": probe.relpath, "lines": contract["lines"]})
        if contract["wrapper_call_present"]:
            wrapper_call_present = True
        if contract["profile_contract_present"]:
            profile_contract_present = True

    workspace_contract_ok, workspace_contract_evidence = _wrapper_workspace_contract(wrapper_probes)

    hook_hits = _valid_hits(hook_probes)
    wrapper_hits = _valid_hits(wrapper_probes)
    ok = bool(hook_hits) and bool(wrapper_hits) and wrapper_call_present and profile_contract_present
    if hook_exec_required:
        ok = ok and hook_exec_present
    if requires_workspace_contract:
        ok = ok and workspace_contract_ok

    evidence = {
        "hook_hits": hook_hits,
        "hook_template_hits": _valid_hits(hook_template_probes),
        "hook_blocked_hits": _blocked_hits(hook_probes),
        "hook_template_blocked_hits": _blocked_hits(hook_template_probes),
        "wrapper_hits": wrapper_hits,
        "wrapper_template_hits": _valid_hits(wrapper_template_probes),
        "wrapper_template_blocked_hits": _blocked_hits(wrapper_template_probes),
        "legacy_gate_hits": _valid_hits(legacy_gate_probes),
        "legacy_gate_blocked_hits": _blocked_hits(legacy_gate_probes),
        "hook_contract_checked": hook_contract_checked,
        "hook_exec_required": hook_exec_required,
        "hook_exec_present": hook_exec_present,
        "hook_exec_checked": hook_exec_checked,
        "wrapper_call_present": wrapper_call_present,
        "profile_contract_present": profile_contract_present,
        "workspace_contract_required": requires_workspace_contract,
        **workspace_contract_evidence,
        "hook_contexts_checked": hook_contexts_checked,
    }
    return ok, evidence


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def _detect_capabilities(resolved_path: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    vendored_probes = _probe_paths(
        resolved_path,
        ("tools/rocs-cli/VENDORED_HASHES.json",),
        label="vendored hash file",
        load_text=True,
    )
    vendored_probe = vendored_probes[0] if vendored_probes else None
    rocs_cli_vendored = False
    vendored_reason = "missing"
    if vendored_probe is not None:
        if not vendored_probe.valid:
            vendored_reason = str(vendored_probe.blocker or "invalid")
        else:
            rocs_cli_vendored, integrity_lines = verify_vendored_hashes(resolved_path / "tools" / "rocs-cli")
            vendored_reason = "ok" if rocs_cli_vendored else "integrity_failed: " + "; ".join(integrity_lines)

    manifest_probes = _probe_paths(resolved_path, MANIFEST_CANDIDATES, label="ontology manifest", load_text=True)
    manifest_hits = _valid_hits(manifest_probes)
    manifest_contract_ok, manifest_contract_evidence, requires_workspace_contract = _manifest_contract_status(
        manifest_probes
    )
    hook_contract_ok, hook_contract_evidence = _hook_contract_status(
        resolved_path,
        requires_workspace_contract=requires_workspace_contract,
    )

    observed = {
        "rocs_cli_vendored": rocs_cli_vendored,
        "ontology_manifest": bool(manifest_hits) and manifest_contract_ok,
        "rocs_ci_gate": bool(hook_contract_evidence.get("hook_hits")) and hook_contract_ok,
    }

    evidence = {
        "rocs_cli_vendored": {
            "hash_file": "tools/rocs-cli/VENDORED_HASHES.json",
            "status": vendored_reason,
            "blocked_hits": _blocked_hits(vendored_probes),
        },
        "ontology_manifest": {
            "hits": manifest_hits,
            **manifest_contract_evidence,
        },
        "rocs_ci_gate": {
            **hook_contract_evidence,
        },
    }
    return observed, evidence

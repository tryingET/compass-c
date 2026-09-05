from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from rocs_cli import __version__
from rocs_cli.authority import authority_receipt_payload, can_write_authority_receipt, write_authority_receipt
from rocs_cli.errors import RocsCliError
from rocs_cli.layers import dist_dir, repo_root as _repo_root
from rocs_cli.managed_surface import ensure_managed_output_dir, ensure_managed_output_file
from rocs_cli.repo_view import RepoView, load_repo_view
from rocs_cli.rules import Finding

_DEFAULT_ENV_REL = Path("holdingco/governance-kernel/.env")

def get_console():
    from rocs_cli import cli
    return cli.console


def _discover_default_env_file(*, repo_root: Path | None) -> Path | None:
    env_from_var = os.environ.get("ROCS_ENV_FILE") or ""
    if env_from_var.strip():
        return Path(env_from_var).expanduser()
    if repo_root is None:
        return None

    repo_env = repo_root / ".env"
    if repo_env.exists():
        return repo_env

    for p in [repo_root, *repo_root.parents]:
        cand = p / _DEFAULT_ENV_REL
        if cand.exists():
            return cand

    return None

def _maybe_load_env_file(env_file: str | None, *, repo_root: Path | None) -> None:
    p = Path(env_file).expanduser() if env_file else _discover_default_env_file(repo_root=repo_root)
    if not p:
        return
    from rocs_cli.env import load_env_file

    load_env_file(p)

def _load_view(args: argparse.Namespace, *, load_docs: bool = True, repo: str | Path | None = None) -> RepoView:
    repo_root = _repo_root(str(repo if repo is not None else args.repo))
    _maybe_load_env_file(getattr(args, "env_file", None), repo_root=repo_root)
    return load_repo_view(
        repo_root,
        profile=getattr(args, "profile", None),
        resolve_refs=bool(getattr(args, "resolve_refs", False)),
        workspace_root=getattr(args, "workspace_root", None),
        workspace_ref_mode=getattr(args, "workspace_ref_mode", None),
        only=getattr(args, "only", None),
        layer=getattr(args, "layer", None),
        load_docs=load_docs,
    )

def _findings_to_json(findings: list[Finding]) -> list[dict]:
    return [f.to_dict() for f in findings]

def _print_findings(findings: list[Finding]) -> None:
    for f in findings:
        loc = f.path or ""
        if loc:
            get_console().print(f"- {f.rule_id} {f.severity} {loc}: {f.message}")
        else:
            get_console().print(f"- {f.rule_id} {f.severity}: {f.message}")

def _ensure_dist_dir(repo: Path, *, label: str) -> Path:
    return ensure_managed_output_dir(repo, dist_dir(repo), label=label)

def _write_resolve_artifact(repo: Path, *, layers, profile: str | None) -> Path:
    dist = _ensure_dist_dir(repo, label="resolve artifact dir")
    entries = []
    for layer_spec in layers:
        entries.append(
            {
                "name": layer_spec.name,
                "kind": layer_spec.kind,
                "origin": layer_spec.origin,
                "source": layer_spec.source,
                "src_root": str(layer_spec.src_root),
                "source_contract": layer_spec.source_contract,
            }
        )
    entries.sort(key=lambda e: str(e.get("name") or ""))
    payload = {
        "schema_version": 2,
        "version": __version__,
        "repo": str(repo),
        "profile": profile,
        "layers": entries,
    }
    out = ensure_managed_output_file(repo, dist / "resolve.json", label="resolve artifact")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    return out

def _clear_build_artifacts(repo: Path) -> None:
    dist = dist_dir(repo)
    for name in ("resolve.json", "summary.json", "id_index.json"):
        (dist / name).unlink(missing_ok=True)

def _write_authority_receipt_if_possible(
    repo: Path,
    *,
    command: str,
    ok: bool,
    profile: str | None,
    resolve_refs_requested: bool,
    workspace_ref_mode: str,
    layers,
    result: dict | None = None,
    error: RocsCliError | None = None,
    source_contract_conformance: dict | None = None,
) -> dict[str, Path] | None:
    if not can_write_authority_receipt(repo):
        return None
    payload = authority_receipt_payload(
        repo,
        command=command,
        ok=ok,
        profile=profile,
        resolve_refs_requested=resolve_refs_requested,
        workspace_ref_mode=workspace_ref_mode,
        layers=list(layers),
        result=result,
        error=error,
        source_contract_conformance=source_contract_conformance,
    )
    return write_authority_receipt(repo, payload)

def _finding_summary(findings: list[Finding]) -> dict[str, int]:
    return {
        "finding_count": len(findings),
        "error_count": sum(1 for f in findings if f.severity == "error"),
        "warning_count": sum(1 for f in findings if f.severity == "warn"),
    }

def _diff_sets(a: set[str], b: set[str]) -> tuple[list[str], list[str]]:
    removed = sorted(a - b)
    added = sorted(b - a)
    return removed, added

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocs_cli import __version__
from rocs_cli.cache import cache_dir, clear_cache, list_cache_entries, prune_cache
from rocs_cli.cli_support import (
    _diff_sets,
    _ensure_dist_dir,
    _findings_to_json,
    _load_view,
    _maybe_load_env_file,
    _print_findings,
    get_console,
)
from rocs_cli.errors import RocsCliError
from rocs_cli.graph import build_edges, collapse_nodes, compute_layout, write_graph
from rocs_cli.inverses import check_inverses
from rocs_cli.layers import parse_ref_locator, repo_root as _repo_root, resolve_layers, resolve_ref_repo_root
from rocs_cli.lint import lint_docs
from rocs_cli.managed_surface import ensure_managed_output_file
from rocs_cli.model import collect_docs
from rocs_cli.normalize import normalize_tree
from rocs_cli.pack import build_pack, pack_config_from_profile
from rocs_cli.rules import RULES
from rocs_cli.rulesets import behavior_for_ruleset, effective_ruleset
from rocs_cli.vendored import verify_vendored_hashes

def cmd_rules(args: argparse.Namespace) -> int:
    rules = sorted(RULES.values(), key=lambda r: r.rule_id)
    payload = {
        "rules": [
            {
                "rule_id": r.rule_id,
                "default_severity": r.default_severity,
                "summary": r.summary,
            }
            for r in rules
        ]
    }
    if args.json:
        get_console().print_json(json.dumps(payload))
        return 0
    for r in rules:
        get_console().print(f"{r.rule_id} {r.default_severity} {r.summary}")
    return 0

def cmd_explain(args: argparse.Namespace) -> int:
    rule_id = str(args.rule_id)
    r = RULES.get(rule_id)
    if r is None:
        raise SystemExit(f"unknown rule id: {rule_id}")
    payload = {
        "rule": {
            "rule_id": r.rule_id,
            "default_severity": r.default_severity,
            "summary": r.summary,
            "suppress": {"field": "ont.lint_ignore", "value": r.rule_id},
        }
    }
    if args.json:
        get_console().print_json(json.dumps(payload))
        return 0
    get_console().print(f"{r.rule_id} ({r.default_severity})")
    get_console().print(r.summary)
    get_console().print("")
    get_console().print("suppress:")
    get_console().print(f"- add to `ont.lint_ignore`: {r.rule_id!r}")
    return 0

def cmd_pack(args: argparse.Namespace) -> int:
    view = _load_view(args)
    cid = args.ont_id
    doc = view.concepts.get(cid) or view.relations.get(cid)
    if not doc:
        raise RocsCliError(kind="not_found", message=f"unknown ont_id: {cid}", exit_code=2, details={"ont_id": cid})

    rel_types: set[str] | None = None
    if args.rel_types:
        rel_types = {x.strip() for x in args.rel_types.split(",") if x.strip()}

    cfg = pack_config_from_profile(
        profile_def=view.meta.get("profile_def") if isinstance(view.meta, dict) else None,
        overrides={
            "max_depth": args.depth,
            "rel_types": rel_types,
            "include_relation_defs": True if args.include_relation_defs else None,
            "max_docs": args.max_docs,
            "max_bytes": args.max_bytes,
        },
    )

    packed, pack_meta = build_pack(concepts=view.concepts, relations=view.relations, root_id=cid, config=cfg)
    if args.json:
        payload: dict[str, object] = {
            "repo": str(view.repo),
            "profile": view.meta.get("profile"),
            "pack": pack_meta,
            "docs": [{"ont_id": d.ont_id, "kind": d.kind, "path": d.path} for d in packed],
        }
        conformance = view.source_conformance("pack", complete_success=True)
        if conformance is not None:
            payload["source_contract_conformance"] = conformance
        get_console().print_json(json.dumps(payload))
        return 0

    first = True
    for d in packed:
        if not first:
            get_console().print("\n---\n")
        first = False
        get_console().print(d.path)
        get_console().print(d.text)
    return 0

def cmd_lint(args: argparse.Namespace) -> int:
    view = _load_view(args)
    profile_def = view.meta.get("profile_def") if isinstance(view.meta, dict) else None
    ruleset_name = effective_ruleset(cli_ruleset=getattr(args, "ruleset", None), profile_def=profile_def)
    ruleset_behavior = behavior_for_ruleset(ruleset_name)
    strict_placeholders = bool(args.strict_placeholders or ruleset_behavior.strict_placeholders)
    fail_on_warn = bool(args.fail_on_warn or ruleset_behavior.fail_on_warn)

    findings = lint_docs(view.concepts, view.relations, strict_placeholders=strict_placeholders)
    rule_filter: set[str] | None = None
    if args.rules and args.rules != "all":
        rule_filter = {x.strip() for x in args.rules.split(",") if x.strip()}
        unknown = sorted([r for r in rule_filter if r not in RULES])
        if unknown:
            raise SystemExit(f"unknown lint rule ids: {unknown}")
    if rule_filter is not None:
        findings = [f for f in findings if f.rule_id in rule_filter]
    failed = bool(findings and fail_on_warn)
    if args.json:
        payload: dict[str, object] = {"findings": _findings_to_json(findings)}
        conformance = view.source_conformance("lint", complete_success=not failed)
        if conformance is not None:
            payload["source_contract_conformance"] = conformance
        get_console().print_json(json.dumps(payload))
    else:
        if findings:
            get_console().print("[yellow]rocs lint[/yellow]")
            _print_findings(findings)
        else:
            get_console().print("[green]rocs lint: OK[/green]")
    if failed:
        return 1
    return 0

def cmd_check_inverses(args: argparse.Namespace) -> int:
    view = _load_view(args)
    findings = check_inverses(view.relations, fix=args.fix)
    failed = any(f.severity == "error" for f in findings)
    if args.json:
        payload: dict[str, object] = {"findings": _findings_to_json(findings)}
        conformance = view.source_conformance("check-inverses", complete_success=not failed)
        if conformance is not None:
            payload["source_contract_conformance"] = conformance
        get_console().print_json(json.dumps(payload))
    else:
        if not findings:
            get_console().print("[green]rocs check-inverses: OK[/green]")
        else:
            get_console().print("[yellow]rocs check-inverses[/yellow]")
            _print_findings(findings)
    if failed:
        return 1
    return 0

def cmd_graph(args: argparse.Namespace) -> int:
    view = _load_view(args)
    rel_filter: set[str] | None = None
    if args.scope == "taxonomy":
        rel_filter = {"is_a"}
    if args.relation:
        rel_filter = {args.relation}
    edges = build_edges(view.concepts, rel_filter=rel_filter)
    nodes = sorted(set(view.concepts.keys()) | {edge.src for edge in edges} | {edge.dst for edge in edges})
    if args.collapse_prefix:
        nodes, edges = collapse_nodes(nodes, edges, prefixes=args.collapse_prefix.split(","))
    layout = compute_layout(nodes, edges, layout=args.layout)
    if args.out:
        out = Path(args.out)
    else:
        dist = _ensure_dist_dir(view.repo, label="graph output dir")
        if args.json:
            out = ensure_managed_output_file(view.repo, dist / "graph.json", label="graph artifact")
        elif args.format == "dot":
            out = ensure_managed_output_file(view.repo, dist / "graph.dot", label="graph artifact")
        elif args.format == "excalidraw-cli-json":
            out = ensure_managed_output_file(view.repo, dist / "graph.excalidraw-cli.json", label="graph artifact")
        else:
            out = ensure_managed_output_file(view.repo, dist / "graph.excalidraw.json", label="graph artifact")
    direction = "LR" if args.layout == "dag" else "TB"
    fmt = "json" if args.json else args.format
    write_graph(out, fmt=fmt, nodes=nodes, edges=edges, layout=layout, direction=direction)
    if args.json:
        payload: dict[str, object] = {"ok": True, "out": str(out), "format": fmt}
        conformance = view.source_conformance("graph", complete_success=True)
        if conformance is not None:
            payload["source_contract_conformance"] = conformance
        get_console().print_json(json.dumps(payload))
    else:
        get_console().print(f"[green]wrote[/green] {out}")
    return 0

def cmd_cache(args: argparse.Namespace) -> int:
    if args.subcmd == "dir":
        get_console().print(str(cache_dir()))
        return 0
    if args.subcmd == "ls":
        entries = list_cache_entries()
        for e in entries:
            get_console().print(f"{e.bytes:>12}  {e.path}")
        return 0
    if args.subcmd == "clear":
        clear_cache()
        get_console().print("[green]cache cleared[/green]")
        return 0
    if args.subcmd == "prune":
        removed = prune_cache(max_age_days=int(args.max_age_days))
        get_console().print(f"[green]pruned[/green] {removed}")
        return 0
    raise SystemExit(f"unknown cache subcmd: {args.subcmd}")

def cmd_vendored_check(args: argparse.Namespace) -> int:
    vendored_dir = Path(args.vendored_dir).resolve()
    ok, lines = verify_vendored_hashes(vendored_dir)
    if ok:
        get_console().print("[green]vendored-check: OK[/green]")
        return 0
    get_console().print("[red]vendored-check: FAIL[/red]")
    for ln in lines[:200]:
        get_console().print(f"- {ln}")
    if len(lines) > 200:
        get_console().print(f"... ({len(lines) - 200} more)")
    return 1

def cmd_normalize(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo)
    _maybe_load_env_file(getattr(args, "env_file", None), repo_root=repo)
    layers, _meta = resolve_layers(
        repo,
        profile=args.profile,
        resolve_refs=args.resolve_refs,
        workspace_root=args.workspace_root,
        workspace_ref_mode=args.workspace_ref_mode,
        only="path",
        layer=args.layer,
    )
    concepts, relations = collect_docs(layers)
    admitted = [*concepts.values(), *relations.values()]
    changed_paths: list[str] = []
    for layer_spec in layers:
        layer_docs = [doc for doc in admitted if doc.layer_name == layer_spec.name]
        for change in normalize_tree(layer_spec.src_root, apply=args.apply, documents=layer_docs):
            if change.changed:
                changed_paths.append(str(change.path))

    if changed_paths and not args.apply:
        get_console().print("[yellow]rocs normalize: changes needed (rerun with --apply)[/yellow]")
        for p in changed_paths[:50]:
            get_console().print(f"- {p}")
        if len(changed_paths) > 50:
            get_console().print(f"... ({len(changed_paths) - 50} more)")
        return 2

    if changed_paths and args.apply:
        get_console().print(f"[green]rocs normalize: applied[/green] ({len(changed_paths)} files)")
    else:
        get_console().print("[green]rocs normalize: OK[/green]")
    return 0

def cmd_diff(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo)
    _maybe_load_env_file(getattr(args, "env_file", None), repo_root=repo)
    baseline = args.baseline.strip()
    if not args.resolve_refs:
        raise SystemExit("rocs diff requires --resolve-refs to resolve a <repo:...@...> baseline")
    parsed = parse_ref_locator(baseline)
    if parsed is None:
        raise SystemExit("--baseline must be a <repo:...@...> locator")

    base_repo, _base_source, _base_notes = resolve_ref_repo_root(
        baseline,
        resolve_refs=args.resolve_refs,
        workspace_root=args.workspace_root,
        workspace_ref_mode=args.workspace_ref_mode,
    )

    cur_view = _load_view(args)
    base_view = _load_view(args, repo=base_repo)

    cur_edges = {f"{e.src}|{e.rel}|{e.dst}" for e in build_edges(cur_view.concepts, rel_filter=None)}
    base_edges = {f"{e.src}|{e.rel}|{e.dst}" for e in build_edges(base_view.concepts, rel_filter=None)}

    removed_concepts, added_concepts = _diff_sets(set(base_view.concepts.keys()), set(cur_view.concepts.keys()))
    removed_relations, added_relations = _diff_sets(set(base_view.relations.keys()), set(cur_view.relations.keys()))
    removed_edges, added_edges = _diff_sets(base_edges, cur_edges)

    breaking = {
        "removed_concepts": removed_concepts,
        "removed_relations": removed_relations,
        "removed_edges": removed_edges,
    }

    payload = {
        "schema_version": 1,
        "version": __version__,
        "repo": str(repo),
        "profile": cur_view.meta.get("profile")
        if isinstance(cur_view.meta, dict) and isinstance(cur_view.meta.get("profile"), str)
        else None,
        "baseline": baseline,
        "baseline_repo": str(base_repo),
        "diff": {
            "concepts": {"removed": removed_concepts, "added": added_concepts},
            "relations": {"removed": removed_relations, "added": added_relations},
            "edges": {"removed": removed_edges, "added": added_edges},
        },
        "breaking": breaking,
    }

    dist = _ensure_dist_dir(repo, label="diff output dir")
    out = ensure_managed_output_file(repo, dist / "diff.json", label="diff artifact")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")

    if args.json:
        get_console().print_json(json.dumps(payload))
        return 0 if not (removed_concepts or removed_relations or removed_edges) else 2

    get_console().print(f"baseline: {baseline}")
    get_console().print(f"profile: {payload['profile']}")
    get_console().print(f"wrote: {out}")
    get_console().print(f"concepts: -{len(removed_concepts)} +{len(added_concepts)}")
    get_console().print(f"relations: -{len(removed_relations)} +{len(added_relations)}")
    get_console().print(f"edges: -{len(removed_edges)} +{len(added_edges)}")
    if removed_concepts or removed_relations or removed_edges:
        get_console().print("[yellow]breaking removals detected[/yellow]")
        return 2
    return 0

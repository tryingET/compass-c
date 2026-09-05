from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocs_cli import __version__
from rocs_cli.cli_support import get_console
from rocs_cli.constitution import (
    ConstitutionError,
    challenge_candidate,
    differential,
    generate_mutants,
    pareto_frontier,
    strict_json_load,
    validate_candidate,
)
from rocs_cli.contracts import command_contract
from rocs_cli.intelligence import (
    compile_plan,
    create_capsule,
    load_json as load_membrane_json,
    validate_capsule,
    validate_proposal,
    write_compiled_plan,
)
from rocs_cli.layers import repo_root as _repo_root
from rocs_cli.transactions import (
    apply_transaction,
    prepare_transaction,
    rollback_transaction,
    simulate_transaction,
    verify_receipt,
)

def cmd_version(_args: argparse.Namespace) -> int:
    get_console().print(f"rocs-cli {__version__}")
    return 0

def cmd_contracts(_args: argparse.Namespace) -> int:
    payload = {**command_contract(), "tool": {"name": "rocs-cli", "version": __version__}}
    get_console().print_json(json.dumps(payload, sort_keys=True))
    return 0

def cmd_constitution(args: argparse.Namespace) -> int:
    def load(name: str):
        values = getattr(args, name)
        if type(values) is not list or len(values) != 1:
            raise ConstitutionError(f"--{name.replace('_', '-')} must be supplied exactly once")
        with Path(values[0]).open("r", encoding="utf-8") as handle:
            return strict_json_load(handle)

    if args.constitution_cmd == "validate":
        payload = validate_candidate(load("candidate"))
    elif args.constitution_cmd == "challenge":
        payload = challenge_candidate(load("candidate"))
    elif args.constitution_cmd == "differential":
        payload = differential(load("candidate_a"), load("candidate_b"), load("subjects"))
    else:
        payload = generate_mutants(load("contract"), load("acceptance"), load("corpus"))
    get_console().print_json(json.dumps(payload, sort_keys=True))
    return 0 if payload.get("fixtures_consistent", True) else 1

def cmd_repair_market(args: argparse.Namespace) -> int:
    if type(args.market) is not list or len(args.market) != 1:
        raise ConstitutionError("--market must be supplied exactly once")
    with Path(args.market[0]).open("r", encoding="utf-8") as handle:
        payload = pareto_frontier(strict_json_load(handle))
    get_console().print_json(json.dumps(payload, sort_keys=True))
    return 0

def cmd_wave1(args: argparse.Namespace) -> int:
    from rocs_cli import wave1

    op = args.operation
    if op in {"bootstrap", "converge"}:
        payload = wave1.bootstrap(Path(args.target), args.repo_class, dry_run=args.dry_run, converge=op == "converge")
        get_console().print_json(json.dumps(payload))
        return 0
    if op == "vendor":
        payload = wave1.vendor(_repo_root("."), Path(args.target), version=args.release_version, dry_run=args.dry_run)
        get_console().print_json(json.dumps(payload))
        return 0
    if op in {"release-plan", "release-apply"}:
        function = wave1.release_plan if op == "release-plan" else wave1.release_apply
        get_console().print_json(json.dumps(function(args.release_version, project=_repo_root("."))))
        return 0
    if op == "verify":
        payload, code = wave1.verify(Path(args.path))
    elif op == "cleanup":
        payload, code = wave1.cleanup(Path(args.repo), dry_run=args.dry_run), 0
    elif op == "doctor":
        payload, code = wave1.doctor(Path(args.repo))
    elif op == "generate":
        payload, code = wave1.generate(Path(args.out), args.count), 0
    elif op == "benchmark":
        payload, code = wave1.benchmark(args.command, args.count, args.runs), 0
    else:
        raise ValueError(f"unknown operation: {op}")
    get_console().print_json(json.dumps(payload))
    return code

def cmd_fleet(args: argparse.Namespace) -> int:
    from rocs_cli import fleet

    root, policy = Path(args.workspace_root), Path(args.policy)
    if args.fleet_cmd == "observe":
        payload, code = fleet.observe(root, policy, report_only=args.report_only)
    elif args.fleet_cmd == "plan":
        payload, code = fleet.plan(root, policy)
    elif args.fleet_cmd == "apply":
        payload, code = fleet.apply(root, policy, dry_run=args.dry_run)
    elif args.fleet_cmd == "run":
        payload, code = fleet.run(root, policy, mode=args.mode)
    else:
        raise ValueError(f"unknown fleet operation: {args.fleet_cmd}")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    destination = args.json
    if destination and destination != "-":
        out = Path(destination).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, "utf-8")
    else:
        print(text, end="")
    if getattr(args, "markdown", None):
        if args.fleet_cmd != "observe":
            raise ValueError("--markdown is supported only by fleet observe")
        md = fleet._render_markdown(payload)
        if args.markdown == "-":
            print(md, end="")
        else:
            Path(args.markdown).expanduser().resolve().write_text(md, "utf-8")
    return code

def cmd_context(args: argparse.Namespace) -> int:
    root = Path(args.root)
    inputs = []
    for spec in args.input:
        if ":" not in spec:
            raise SystemExit("--input must be LAYER:PATH where LAYER is path or ref")
        layer, path = spec.split(":", 1)
        inputs.append((path, layer))
    capsule = create_capsule(root, inputs)
    write_compiled_plan(
        Path(args.artifact_root),
        args.out,
        capsule,
        ontology_root=root,
        capsule=capsule,
        input_files=[root / path for path, _layer in inputs],
    )
    return 0

def cmd_proposal(args: argparse.Namespace) -> int:
    capsule = validate_capsule(load_membrane_json(Path(args.capsule)))
    proposal, digest = validate_proposal(load_membrane_json(Path(args.proposal)), capsule)
    if args.proposal_cmd == "validate":
        get_console().print_json(json.dumps({"ok": True, "proposal_digest": digest}, sort_keys=True))
        return 0
    plan = compile_plan(proposal, digest, capsule, load_membrane_json(Path(args.approval)))
    write_compiled_plan(
        Path(args.artifact_root),
        args.out,
        plan,
        ontology_root=Path(args.ontology_root),
        capsule=capsule,
        input_files=[Path(args.capsule), Path(args.proposal), Path(args.approval)],
    )
    return 0

def cmd_transaction(args: argparse.Namespace) -> int:
    load = lambda name: load_membrane_json(Path(getattr(args, name)))
    root = Path(args.ontology_root)
    if args.transaction_cmd == "prepare":
        value = prepare_transaction(
            load("plan"), load("capsule"), root, load("effects"), args.owner, load("authority_artifact")
        )
        write_compiled_plan(
            Path(args.artifact_root),
            args.out,
            value,
            ontology_root=root,
            capsule=validate_capsule(load("capsule")),
            input_files=[Path(args.plan), Path(args.capsule), Path(args.effects)],
        )
        return 0
    if args.transaction_cmd == "simulate":
        value = simulate_transaction(
            load("transaction"), load("plan"), load("capsule"), root, load("authority_artifact")
        )
    elif args.transaction_cmd == "apply":
        value = apply_transaction(
            load("transaction"),
            load("plan"),
            load("capsule"),
            load("approval"),
            root,
            Path(args.receipt_root),
            load("authority_artifact"),
            inject_failure=args.inject_failure,
        )
    elif args.transaction_cmd == "verify":
        value = verify_receipt(load("receipt"), load("transaction"), root)
    else:
        value = rollback_transaction(load("receipt"), load("transaction"), root)
    get_console().print_json(json.dumps(value, sort_keys=True))
    return 0

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os

from rich.console import Console

from rocs_cli import __version__
from rocs_cli.cli_ontology_lifecycle import cmd_build, cmd_resolve, cmd_summary, cmd_validate
from rocs_cli.cli_ontology_utility import (
    cmd_cache,
    cmd_check_inverses,
    cmd_diff,
    cmd_explain,
    cmd_graph,
    cmd_lint,
    cmd_normalize,
    cmd_rules,
    cmd_vendored_check,
)
from rocs_cli.cli_semantic_commands import register_semantic_commands
from rocs_cli.cli_semantic_router import parse_route_args
from rocs_cli.cli_platform import (
    cmd_constitution,
    cmd_context,
    cmd_contracts,
    cmd_fleet,
    cmd_proposal,
    cmd_repair_market,
    cmd_transaction,
    cmd_version,
    cmd_wave1,
)
from rocs_cli.cli_support import (
    _DEFAULT_ENV_REL,
    _clear_build_artifacts,
    _diff_sets,
    _discover_default_env_file,
    _ensure_dist_dir,
    _finding_summary,
    _findings_to_json,
    _load_view,
    _maybe_load_env_file,
    _print_findings,
    _write_authority_receipt_if_possible,
    _write_resolve_artifact,
)
from rocs_cli.errors import RocsCliError
from rocs_cli.validation_service import _schema_validation_result

console = Console()


class _StrictArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = _StrictArgumentParser(prog="rocs")
    parser.add_argument("--version", action="version", version=f"rocs-cli {__version__}")
    parser.add_argument("--debug", action="store_true", help="show full tracebacks on error")
    parser.add_argument("--no-index-cache", action="store_true", help="disable incremental doc/index cache (debugging)")
    parser.add_argument("--index-cache-debug", action="store_true", help="emit index-cache hit/miss stats to stderr")

    p_resolve_common = argparse.ArgumentParser(add_help=False)
    p_resolve_common.add_argument(
        "--workspace-root",
        help="workspace root used to satisfy <repo:...@ref> refs locally (or ROCS_WORKSPACE_ROOT)",
    )
    p_resolve_common.add_argument(
        "--workspace-ref-mode",
        choices=["strict", "loose"],
        help="workspace ref mode for local clones: strict requires HEAD matches requested ref (or ROCS_WORKSPACE_REF_MODE)",
    )
    p_resolve_common.add_argument(
        "--show-resolve-sources",
        action="store_true",
        help="show path/workspace source per layer in text output",
    )
    p_resolve_common.add_argument(
        "--show-resolve-details",
        action="store_true",
        help="show workspace skip reasons (and include per-layer details in JSON output)",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("version")
    p.set_defaults(fn=cmd_version)

    p = sub.add_parser("contracts", help="emit the closed machine-readable command contract")
    p.set_defaults(fn=cmd_contracts)

    register_semantic_commands(sub, p_resolve_common)

    p = sub.add_parser("constitution", help="validate and challenge proposal-only constitutional rules")
    constitution_sub = p.add_subparsers(dest="constitution_cmd", required=True)
    for name in ("validate", "challenge"):
        p2 = constitution_sub.add_parser(name)
        p2.add_argument("--candidate", action="append", required=True)
        p2.set_defaults(fn=cmd_constitution, machine_json=True)
    p2 = constitution_sub.add_parser("differential")
    p2.add_argument("--candidate-a", action="append", required=True)
    p2.add_argument("--candidate-b", action="append", required=True)
    p2.add_argument("--subjects", action="append", required=True)
    p2.set_defaults(fn=cmd_constitution, machine_json=True)
    p2 = constitution_sub.add_parser("mutate")
    p2.add_argument("--contract", action="append", required=True)
    p2.add_argument("--acceptance", action="append", required=True)
    p2.add_argument("--corpus", action="append", required=True)
    p2.set_defaults(fn=cmd_constitution, machine_json=True)

    p = sub.add_parser("repair-market", help="compute a proposal-only stable Pareto frontier")
    p.add_argument("--market", action="append", required=True)
    p.set_defaults(fn=cmd_repair_market, machine_json=True)

    p = sub.add_parser("context", help="create a deterministic content-addressed context capsule")
    context_sub = p.add_subparsers(dest="context_cmd", required=True)
    p2 = context_sub.add_parser("create")
    p2.add_argument("--root", required=True)
    p2.add_argument("--input", action="append", required=True, metavar="LAYER:PATH")
    p2.add_argument("--artifact-root", required=True, help="existing disjoint root bounding capsule artifacts")
    p2.add_argument("--out", required=True, help="artifact-root-relative output path")
    p2.set_defaults(fn=cmd_context)

    p = sub.add_parser("proposal", help="validate or compile an untrusted proposal without mutation")
    proposal_sub = p.add_subparsers(dest="proposal_cmd", required=True)
    p2 = proposal_sub.add_parser("validate")
    p2.add_argument("--capsule", required=True)
    p2.add_argument("--proposal", required=True)
    p2.set_defaults(fn=cmd_proposal)
    p2 = proposal_sub.add_parser("compile")
    p2.add_argument("--capsule", required=True)
    p2.add_argument("--proposal", required=True)
    p2.add_argument("--approval", required=True)
    p2.add_argument("--ontology-root", required=True, help="source/input root forbidden to compiled artifacts")
    p2.add_argument("--artifact-root", required=True, help="existing disjoint root bounding compiled artifacts")
    p2.add_argument("--out", required=True, help="artifact-root-relative output path")
    p2.set_defaults(fn=cmd_proposal)

    p = sub.add_parser("transaction", help="prepare, simulate, apply, verify, or rollback a semantic transaction")
    transaction_sub = p.add_subparsers(dest="transaction_cmd", required=True)
    p2 = transaction_sub.add_parser("prepare")
    p2.add_argument("--plan", required=True)
    p2.add_argument("--capsule", required=True)
    p2.add_argument("--effects", required=True)
    p2.add_argument("--owner", required=True)
    p2.add_argument("--authority-artifact", required=True)
    p2.add_argument("--ontology-root", required=True)
    p2.add_argument("--artifact-root", required=True)
    p2.add_argument("--out", required=True)
    p2.set_defaults(fn=cmd_transaction)
    p2 = transaction_sub.add_parser("simulate")
    p2.add_argument("--transaction", required=True)
    p2.add_argument("--plan", required=True)
    p2.add_argument("--capsule", required=True)
    p2.add_argument("--authority-artifact", required=True)
    p2.add_argument("--ontology-root", required=True)
    p2.set_defaults(fn=cmd_transaction)
    p2 = transaction_sub.add_parser("apply")
    p2.add_argument("--transaction", required=True)
    p2.add_argument("--plan", required=True)
    p2.add_argument("--capsule", required=True)
    p2.add_argument("--approval", required=True)
    p2.add_argument("--authority-artifact", required=True)
    p2.add_argument("--ontology-root", required=True)
    p2.add_argument("--receipt-root", required=True)
    p2.add_argument("--inject-failure", help=argparse.SUPPRESS)
    p2.set_defaults(fn=cmd_transaction)
    for name in ("verify", "rollback"):
        p2 = transaction_sub.add_parser(name)
        p2.add_argument("--receipt", required=True)
        p2.add_argument("--transaction", required=True)
        p2.add_argument("--ontology-root", required=True)
        p2.set_defaults(fn=cmd_transaction)

    p = sub.add_parser("fleet", help="fleet observation and convergence")
    fleet_sub = p.add_subparsers(dest="fleet_cmd", required=True)
    p2 = fleet_sub.add_parser("observe", help="audit fleet capabilities deterministically")
    p2.add_argument("--workspace-root", required=True)
    p2.add_argument("--policy", required=True)
    p2.add_argument("--json", nargs="?", const="-", default=None, metavar="PATH")
    p2.add_argument("--markdown", nargs="?", const="-", default=None, metavar="PATH")
    p2.add_argument("--report-only", action="store_true")
    p2.set_defaults(fn=cmd_fleet)
    for name in ("plan", "apply", "run"):
        p2 = fleet_sub.add_parser(name, help=f"{name} deterministic fleet convergence")
        p2.add_argument("--workspace-root", required=True)
        p2.add_argument("--policy", required=True)
        p2.add_argument("--json", nargs="?", const="-", default=None)
        if name == "apply":
            p2.add_argument("--dry-run", action="store_true")
        if name == "run":
            p2.add_argument("--mode", choices=["audit-only", "patch", "apply"], default="apply")
        p2.set_defaults(fn=cmd_fleet)

    for name in ("bootstrap", "converge"):
        p = sub.add_parser(name, help=f"repository {name}")
        p.add_argument("target")
        p.add_argument("--class", dest="repo_class", required=True, choices=["required", "optional", "ontology_repo"])
        p.add_argument("--dry-run", action="store_true")
        p.set_defaults(fn=cmd_wave1, operation=name)
    p = sub.add_parser("vendor", help="publish a pinned self-contained consumer artifact")
    p.add_argument("target")
    p.add_argument("--release-version")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_wave1, operation="vendor")
    p = sub.add_parser("release", help="plan or apply an explicit release")
    release_sub = p.add_subparsers(dest="release_cmd", required=True)
    for name in ("plan", "apply"):
        p2 = release_sub.add_parser(name)
        p2.add_argument("--version", dest="release_version", required=True)
        p2.set_defaults(fn=cmd_wave1, operation=f"release-{name}")
    p = sub.add_parser("verify", help="verify pinned consumer identity and hashes")
    p.add_argument("path")
    p.set_defaults(fn=cmd_wave1, operation="verify")
    p = sub.add_parser("cleanup", help="safely remove managed build outputs")
    p.add_argument("--repo", default=".")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_wave1, operation="cleanup")
    p = sub.add_parser("doctor", help="check standalone consumer and tool identity")
    p.add_argument("--repo", default=".")
    p.set_defaults(fn=cmd_wave1, operation="doctor")
    p = sub.add_parser("generate", help="generate a deterministic benchmark repository")
    p.add_argument("--out", required=True)
    p.add_argument("--count", type=int, default=200)
    p.set_defaults(fn=cmd_wave1, operation="generate")
    p = sub.add_parser("benchmark", help="benchmark an importable ROCS capability")
    p.add_argument("--command", choices=["build", "validate", "lint"], default="build")
    p.add_argument("--count", type=int, default=500)
    p.add_argument("--runs", type=int, default=7)
    p.set_defaults(fn=cmd_wave1, operation="benchmark")

    p = sub.add_parser("rules")
    p.add_argument("--json", action="store_true", help="emit JSON output")
    p.set_defaults(fn=cmd_rules)

    p = sub.add_parser("explain")
    p.add_argument("rule_id")
    p.add_argument("--json", action="store_true", help="emit JSON output")
    p.set_defaults(fn=cmd_explain)

    p = sub.add_parser("resolve", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument("--json", action="store_true", help="emit JSON output")
    p.add_argument("--write-dist", action="store_true", help="write managed dist/resolve.json artifact")
    p.set_defaults(fn=cmd_resolve)

    p = sub.add_parser("summary", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument("--json", action="store_true", help="emit JSON output")
    p.set_defaults(fn=cmd_summary)

    p = sub.add_parser("validate", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--strict-placeholders", action="store_true", help="fail if any <...> placeholders exist")
    p.add_argument("--ruleset", choices=["dev", "strict"], help="ruleset defaults (or rocs.profiles.<name>.ruleset)")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument(
        "--validate-deps",
        action="store_true",
        help="also enforce strict schema rules on dependency layers (ref layers); default: validate path layers only",
    )
    p.add_argument("--json", action="store_true", help="emit JSON result")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("diff", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--baseline", required=True, help="baseline <repo:...@ref> to diff against")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument("--json", action="store_true", help="emit JSON diff")
    p.set_defaults(fn=cmd_diff)

    p = sub.add_parser("lint", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument("--strict-placeholders", action="store_true", help="treat placeholders in bodies as lint warnings")
    p.add_argument("--rules", default="all", help="comma-separated rule ids (or 'all')")
    p.add_argument("--json", action="store_true", help="emit JSON result")
    p.add_argument("--fail-on-warn", action="store_true", help="exit non-zero if warnings exist")
    p.add_argument("--ruleset", choices=["dev", "strict"], help="ruleset defaults (or rocs.profiles.<name>.ruleset)")
    p.set_defaults(fn=cmd_lint)

    p = sub.add_parser("check-inverses", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument("--fix", action="store_true", help="apply safe fixes to local/path layer relation docs")
    p.add_argument("--json", action="store_true", help="emit JSON result")
    p.set_defaults(fn=cmd_check_inverses)

    p = sub.add_parser("graph", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument("--scope", choices=["all", "taxonomy"], default="all")
    p.add_argument("--relation", help="only include this relation label (e.g. is_a)")
    p.add_argument("--collapse-prefix", help="comma-separated prefixes to collapse (e.g. co.software)")
    p.add_argument("--layout", choices=["grid", "dag"], default="grid")
    p.add_argument("--format", choices=["excalidraw", "excalidraw-cli-json", "dot"], default="excalidraw")
    p.add_argument("--json", action="store_true", help="emit JSON output (writes graph.json by default)")
    p.add_argument("--out", help="output path (default: managed dist/graph.<fmt>.*)")
    p.set_defaults(fn=cmd_graph)

    p = sub.add_parser("build", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--only", help="filter layers: path|ref")
    p.add_argument("--layer", help="filter a specific layer name")
    p.add_argument("--clean", action="store_true", help="remove the managed dist directory before building")
    p.add_argument("--json", action="store_true", help="emit JSON output")
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser("vendored-check")
    p.add_argument(
        "--vendored-dir", required=True, help="path to vendored rocs-cli dir (contains VENDORED_HASHES.json)"
    )
    p.set_defaults(fn=cmd_vendored_check)

    p = sub.add_parser("cache")
    sub2 = p.add_subparsers(dest="subcmd", required=True)
    p2 = sub2.add_parser("dir")
    p2.set_defaults(fn=cmd_cache)
    p2 = sub2.add_parser("ls")
    p2.set_defaults(fn=cmd_cache)
    p2 = sub2.add_parser("clear")
    p2.set_defaults(fn=cmd_cache)
    p2 = sub2.add_parser("prune")
    p2.add_argument("--max-age-days", default="30")
    p2.set_defaults(fn=cmd_cache)

    p = sub.add_parser("normalize", parents=[p_resolve_common])
    p.add_argument("--repo", default=".", help="repo root path")
    p.add_argument("--profile", help="manifest profile name (defaults to rocs.profiles.default)")
    p.add_argument(
        "--resolve-refs",
        action="store_true",
        help="resolve <repo:...@...> refs from the local workspace",
    )
    p.add_argument("--env-file", help="dotenv file to load into environment (for local config)")
    p.add_argument("--layer", help="only normalize a specific layer name (path layers only)")
    p.add_argument("--apply", action="store_true", help="apply changes (default: check only)")
    p.set_defaults(fn=cmd_normalize)

    return parser

def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    effective_argv = list(argv) if argv is not None else __import__("sys").argv[1:]
    command = next((token for token in effective_argv if not token.startswith("-")), None)
    if command == "discover":
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                args, unknown = parser.parse_known_args(effective_argv)
        except SystemExit as error:
            if error.code == 0:
                raise
            from rocs_cli.discovery import DiscoveryError, error_envelope
            from rocs_cli.semantic_protocol import caller_request_identity
            raw: bytes | None = None
            try:
                if "--request-json=-" in effective_argv:
                    raw = __import__("sys").stdin.buffer.read(262_145)
                else:
                    index = effective_argv.index("--request-json")
                    if effective_argv[index + 1] == "-":
                        raw = __import__("sys").stdin.buffer.read(262_145)
            except (ValueError, IndexError, AttributeError):
                raw = None
            digest = caller_request_identity(raw)[1] if raw is not None and len(raw) <= 262_144 else None
            print(json.dumps(error_envelope(DiscoveryError("invalid_request", caller_request_digest=digest)), separators=(",", ":")))
            raise SystemExit(1) from None
        setattr(args, "parser_unknown", unknown)
    elif command == "route":
        args = parse_route_args(parser, effective_argv)
    else:
        args = parser.parse_args(effective_argv)
    debug = bool(getattr(args, "debug", False))
    if bool(getattr(args, "no_index_cache", False)):
        os.environ["ROCS_INDEX_CACHE"] = "0"
    if bool(getattr(args, "index_cache_debug", False)):
        os.environ["ROCS_INDEX_CACHE_DEBUG"] = "1"

    def _wants_json() -> bool:
        return bool(getattr(args, "json", False) or getattr(args, "machine_json", False))

    def _emit_error(kind: str, message: str, *, details: dict | None = None) -> None:
        if _wants_json():
            payload: dict = {"ok": False, "error": {"kind": kind, "message": message}}
            if details:
                payload["error"]["details"] = details
            console.print_json(json.dumps(payload))
        else:
            console.print(f"[red]error[/red]: {message}")

    try:
        code = int(args.fn(args))
    except RocsCliError as e:
        if debug:
            raise
        _emit_error(e.kind, e.message, details=e.details)
        raise SystemExit(int(e.exit_code)) from None
    except SystemExit as e:
        if debug:
            raise
        # Normalize our "raise SystemExit('message')" cases into clean CLI output.
        if isinstance(e.code, str) and e.code.strip():
            _emit_error("error", e.code)
            raise SystemExit(1) from None
        raise
    except Exception as e:  # noqa: BLE001
        if debug:
            raise
        _emit_error("internal", str(e))
        raise SystemExit(1) from None
    raise SystemExit(code)

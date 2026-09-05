"""Closed CLI adapter for development-only semantic routing."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

from rocs_cli.discovery import development_tool_identity
from rocs_cli.errors import RocsCliError
from rocs_cli.layers import LayerSpec, repo_root as resolve_repo_root, resolve_layers
from rocs_cli.semantic_router import route
from rocs_cli.semantic_router_policy import capture_policy_bundle
from rocs_cli.semantic_router_protocol import (
    MAX_REQUEST_BYTES,
    RouteProtocolError,
    caller_request_identity,
    error_envelope,
    parse_request_bytes,
    route_capabilities,
)
from rocs_cli.semantic_snapshot import SnapshotError, capture_corpus

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ROUTE_ERROR_KINDS = {"invalid_ontology", "snapshot_changed", "resource_exhausted"}


def _console():
    from rocs_cli.cli import console

    return console


def _emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def _stdin_request(argv: list[str]) -> bytes | None:
    try:
        if "--request-json=-" in argv:
            return sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        index = argv.index("--request-json")
        if argv[index + 1] == "-":
            return sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    except (AttributeError, IndexError, ValueError):
        pass
    return None


def parse_route_args(parser: argparse.ArgumentParser, argv: list[str]) -> argparse.Namespace:
    """Parse route syntax without exposing argparse diagnostics on stderr."""
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            args, unknown = parser.parse_known_args(argv)
    except SystemExit as error:
        if error.code == 0:
            raise
        raw = _stdin_request(argv)
        caller_digest = caller_request_identity(raw)[1] if raw is not None else None
        _emit(error_envelope("invalid_request", caller_digest))
        raise SystemExit(1) from None
    setattr(args, "parser_unknown", unknown)
    setattr(args, "route_argv", list(argv))
    return args


def cmd_route_capabilities(_args: argparse.Namespace) -> int:
    _emit(route_capabilities())
    return 0


def _valid_arguments(args: argparse.Namespace) -> bool:
    argv = getattr(args, "route_argv", [])
    try:
        route_index = argv.index("route")
    except ValueError:
        return False
    prefix, suffix = argv[:route_index], argv[route_index + 1:]
    exact = ("--repo", "--policy-owner-repo-id", "--policy-owner-repo-root", "--routing-policy-root", "--routing-policy", "--routing-provenance", "--request-json", "--tool-kind", "--tool-manifest-digest", "--json", "--no-index-cache", "--no-env-file")
    counts = {name: sum(token == name or token.startswith(name + "=") for token in suffix) for name in exact}
    required_strings = (
        args.repo,
        args.policy_owner_repo_id,
        args.policy_owner_repo_root,
        args.routing_policy_root,
        args.routing_policy,
        args.routing_provenance,
    )
    return (
        not getattr(args, "parser_unknown", [])
        and prefix in ([], ["--debug"])
        and all(count == 1 for count in counts.values())
        and not getattr(args, "index_cache_debug", False)
        and all(type(value) is str and bool(value) for value in required_strings)
        and args.request_json == "-"
        and args.tool_kind == "development_runtime"
        and type(args.tool_manifest_digest) is str
        and _DIGEST_RE.fullmatch(args.tool_manifest_digest) is not None
        and args.json is True
        and args.no_index_cache is True
        and args.no_env_file is True
    )


def cmd_route(args: argparse.Namespace) -> int:
    caller_digest: str | None = None
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        unvalidated, caller_digest = caller_request_identity(raw)
        if unvalidated is None:
            raise RouteProtocolError("invalid_request")
        request = parse_request_bytes(raw)
        if not _valid_arguments(args):
            raise RouteProtocolError("invalid_request")

        supplied_repo = Path(args.repo).absolute()
        if any(path.is_symlink() for path in (supplied_repo, *supplied_repo.parents)):
            raise RouteProtocolError("invalid_ontology")
        repo = resolve_repo_root(args.repo)
        layers, _meta = resolve_layers(
            repo,
            profile=str(request["profile"]),
            resolve_refs=False,
            workspace_root=str(repo),
            workspace_ref_mode="strict",
        )
        if any(layer.kind != "path" or layer.source != "path" for layer in layers):
            raise RouteProtocolError("invalid_ontology")
        layers = [
            LayerSpec(
                layer.name,
                repo / layer.origin,
                layer.origin,
                layer.kind,
                layer.source,
                layer.source_contract,
            )
            for layer in layers
        ]
        corpus = capture_corpus(
            layers,
            profile=str(request["profile"]),
            limits=request["discovery_limits"],
        )
        isolated_roots = tuple(Path(layer.src_root).parent for layer in layers)
        with capture_policy_bundle(
            routing_policy_root=args.routing_policy_root,
            policy_path=args.routing_policy,
            provenance_path=args.routing_provenance,
            owner_repo_id=args.policy_owner_repo_id,
            owner_repo_root=args.policy_owner_repo_root,
            request=request,
            isolated_roots=isolated_roots,
        ) as bundle:
            execution = route(
                corpus,
                request,
                bundle.policy,
                bundle.provenance,
                tool_identity=development_tool_identity(manifest_digest=args.tool_manifest_digest),
            )
        _emit(execution.result)
        return 0
    except RouteProtocolError as error:
        kind = error.kind
    except SnapshotError as error:
        kind = error.kind if error.kind in _ROUTE_ERROR_KINDS else "internal"
    except RocsCliError:
        kind = "invalid_ontology"
    except Exception:
        kind = "internal"
    _emit(error_envelope(kind, caller_digest))
    return 1

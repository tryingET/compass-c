"""Parser registration for discovery, bound packs, and semantic routing."""

from __future__ import annotations

import argparse

from rocs_cli.cli_semantic_discovery import (
    cmd_discover,
    cmd_discover_capabilities,
    cmd_pack_dispatch,
)
from rocs_cli.cli_semantic_router import cmd_route, cmd_route_capabilities


def register_semantic_commands(sub: argparse._SubParsersAction, p_resolve_common: argparse.ArgumentParser) -> None:
    """Register semantic commands without changing existing parser signatures."""
    p = sub.add_parser("discover-capabilities", help="emit semantic discovery protocol capabilities")
    p.add_argument("--json", action="store_true", required=True, help="emit closed JSON protocol output")
    p.set_defaults(fn=cmd_discover_capabilities)

    p = sub.add_parser("discover", help="run deterministic semantic discovery")
    p.add_argument("--repo", nargs="?", const="", default=".", help="repo root path")
    p.add_argument("--request-json", nargs="?", const="", help="read the closed request from stdin")
    p.add_argument("--request-file", nargs="?", const="", help="read a request file for explicit interactive use")
    p.add_argument("--tool-kind", nargs="?", const="")
    p.add_argument("--tool-manifest-digest", nargs="?", const="", help="Pi-verified prepared-runtime manifest digest")
    p.add_argument("--resolve-refs", action="store_true", help="resolve local workspace refs")
    p.add_argument("--workspace-root", nargs="?", const="")
    p.add_argument("--workspace-ref-mode", nargs="?", const="")
    p.add_argument("--json", action="store_true", help="emit closed JSON protocol output")
    p.add_argument("--no-index-cache", action="store_true", help="require cache-disabled discovery")
    p.add_argument("--no-env-file", action="store_true", help="forbid implicit dotenv loading")
    p.set_defaults(fn=cmd_discover)

    p = sub.add_parser("route-capabilities", help="emit semantic route protocol capabilities")
    p.add_argument("--json", action="store_true", required=True, help="emit closed JSON protocol output")
    p.set_defaults(fn=cmd_route_capabilities)

    p = sub.add_parser("route", help="run deterministic development semantic routing")
    p.add_argument("--repo", required=True, help="corpus repo root path")
    p.add_argument("--policy-owner-repo-id", required=True, help="exact synthetic policy owner repository ID")
    p.add_argument("--policy-owner-repo-root", required=True, help="existing local policy owner Git root")
    p.add_argument("--routing-policy-root", required=True, help="existing isolated routing policy directory")
    p.add_argument("--routing-policy", required=True, help="policy-root-relative routing policy file")
    p.add_argument("--routing-provenance", required=True, help="policy-root-relative provenance manifest file")
    p.add_argument("--request-json", required=True, choices=["-"], help="read the closed request only from stdin")
    p.add_argument("--tool-kind", required=True, choices=["development_runtime"])
    p.add_argument("--tool-manifest-digest", required=True, help="Pi-verified prepared-runtime manifest digest")
    p.add_argument("--json", action="store_true", required=True, help="emit closed JSON protocol output")
    p.add_argument("--no-index-cache", action="store_true", required=True, help="require cache-disabled routing")
    p.add_argument("--no-env-file", action="store_true", required=True, help="forbid implicit dotenv loading")
    p.set_defaults(fn=cmd_route)

    p = sub.add_parser("pack", parents=[p_resolve_common])
    p.add_argument("ont_id")
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
    p.add_argument("--depth", type=int, help="relation expansion depth (default: profile pack.max_depth or 0)")
    p.add_argument(
        "--rel-types", help="comma-separated relation labels to follow (default: profile pack.rel_types or all)"
    )
    p.add_argument("--include-relation-defs", action="store_true", help="include relation definition docs used")
    p.add_argument("--max-docs", type=int, help="max docs in pack (default: profile pack.max_docs)")
    p.add_argument("--max-bytes", type=int, help="max UTF-8 bytes in pack (default: profile pack.max_bytes)")
    p.add_argument("--json", action="store_true", help="emit JSON output")
    p.add_argument("--expected-snapshot-digest", help="require an exact fresh corpus snapshot digest")
    p.add_argument("--expected-document-digest", help="require an exact selected root document digest")
    p.add_argument("--no-env-file", action="store_true", help="forbid implicit dotenv loading in bound mode")
    p.add_argument("--no-index-cache", action="store_true", help="disable parsed cache in bound mode")
    p.set_defaults(fn=cmd_pack_dispatch)

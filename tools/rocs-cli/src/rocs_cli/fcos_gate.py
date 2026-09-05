from __future__ import annotations

import re
import textwrap
from typing import Any

from rocs_cli.managed_surface import normalize_shell_lines


FCOS_GATE_HOOK_PATH = ".githooks/pre-push"
FCOS_GATE_HOOK_CANDIDATES: tuple[str, ...] = (FCOS_GATE_HOOK_PATH,)
FCOS_GATE_HOOK_TEMPLATE_CANDIDATES: tuple[str, ...] = (
    ".githooks/pre-push.j2",
    ".githooks/pre-push.jinja",
)

FCOS_CI_WRAPPER_PATH = "scripts/ci/full.sh"
FCOS_CI_WRAPPER_CANDIDATES: tuple[str, ...] = (FCOS_CI_WRAPPER_PATH,)
FCOS_CI_WRAPPER_TEMPLATE_CANDIDATES: tuple[str, ...] = (
    "scripts/ci/full.sh.j2",
    "scripts/ci/full.sh.jinja",
)

LEGACY_FCOS_GATE_CANDIDATES: tuple[str, ...] = (
    "gitlab/ci/rocs.yml",
    "gitlab/ci/rocs.yml.j2",
    "gitlab/ci/rocs.yml.jinja",
    ".gitlab-ci.yml",
    ".gitlab-ci.yml.j2",
    ".gitlab-ci.yml.jinja",
)


def _norm(text: str) -> str:
    return textwrap.dedent(text).strip("\n") + "\n"


FCOS_HOOKS_README = _norm(
    """
    # ROCS local gate hooks

    Enable the checked-in hooks for this repo with:

    ```bash
    git config core.hooksPath .githooks
    ```

    The pre-push hook delegates to `scripts/ci/full.sh` so local gates and Pi-driven runs share one policy surface.
    """
)

_GATE_MODE_DEFAULT_PROFILE = {
    "advisory": "local-dev",
    "strict": "main-strict",
}

_WRAPPER_CALL_RE = re.compile(r"(?:^|\s)(?:(?:bash|sh)\s+)?(?:\./)?scripts/ci/full\.sh(?:\s|$)")
_PROFILE_ASSIGN_RE = re.compile(r"(?:^|\s)ROCS_CI_PROFILE=[^\s]+")
_PROFILE_EXPORT_RE = re.compile(r"^\s*export\s+ROCS_CI_PROFILE=[^\s]+")
_WORKSPACE_ROOT_TOKEN_RE = re.compile(r"ROCS_WORKSPACE_ROOT|--workspace-root")
_WORKSPACE_REF_MODE_TOKEN_RE = re.compile(r"ROCS_WORKSPACE_REF_MODE|--workspace-ref-mode")


def default_profile_for_gate_mode(gate_mode: str) -> str:
    try:
        return _GATE_MODE_DEFAULT_PROFILE[gate_mode]
    except KeyError as exc:
        raise ValueError(f"unsupported gate mode: {gate_mode}") from exc


def render_pre_push_hook(gate_mode: str) -> str:
    default_profile = default_profile_for_gate_mode(gate_mode)
    return _norm(
        f"""
        #!/usr/bin/env bash
        set -euo pipefail

        repo_root="$(cd -- "$(dirname -- "${{BASH_SOURCE[0]}}")/.." && pwd)"
        cd "$repo_root"

        export ROCS_CMD="${{ROCS_CMD:-uv run --frozen --project ./tools/rocs-cli python -m rocs_cli}}"
        export ROCS_CI_PROFILE="${{ROCS_CI_PROFILE:-{default_profile}}}"
        bash scripts/ci/full.sh
        """
    )


def hook_contract_evidence(text: str) -> dict[str, Any]:
    lines = normalize_shell_lines(text)
    wrapper_call_present = any(_WRAPPER_CALL_RE.search(line) for line in lines)
    has_inline_profile = any(_WRAPPER_CALL_RE.search(line) and _PROFILE_ASSIGN_RE.search(line) for line in lines)
    has_export_profile = any(_PROFILE_EXPORT_RE.search(line) for line in lines)
    return {
        "lines": lines,
        "wrapper_call_present": wrapper_call_present,
        "profile_contract_present": has_inline_profile or (wrapper_call_present and has_export_profile),
    }


def wrapper_workspace_contract_evidence(text: str) -> dict[str, Any]:
    lines = normalize_shell_lines(text)
    workspace_root_present = any(_WORKSPACE_ROOT_TOKEN_RE.search(line) for line in lines)
    workspace_ref_mode_present = any(_WORKSPACE_REF_MODE_TOKEN_RE.search(line) for line in lines)
    return {
        "lines": lines,
        "workspace_root_present": workspace_root_present,
        "workspace_ref_mode_present": workspace_ref_mode_present,
        "workspace_contract_ok": workspace_root_present and workspace_ref_mode_present,
    }

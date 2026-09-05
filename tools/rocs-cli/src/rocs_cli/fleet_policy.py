from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rocs_cli.capabilities import CAPABILITY_NAMES, CLASS_REQUIREMENTS
from rocs_cli.fleet_preflight import (
    FleetPreflightError,
    normalize_policy_repo_path,
    read_utf8_text,
)


CAPABILITY_KEYS: tuple[str, ...] = CAPABILITY_NAMES


class PolicyError(ValueError):
    pass


def _load_policy(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PolicyError(f"policy not found: {path}")
    try:
        raw = yaml.safe_load(read_utf8_text(path, label="policy"))
    except FleetPreflightError as exc:
        raise PolicyError(str(exc)) from exc
    except yaml.YAMLError as exc:
        raise PolicyError(f"invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise PolicyError("policy root must be a mapping")
    return raw


def _require_mapping(parent: dict[str, Any], key: str, *, where: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise PolicyError(f"{where}.{key} must be a mapping")
    return value


def _require_list(parent: dict[str, Any], key: str, *, where: str) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        raise PolicyError(f"{where}.{key} must be a list")
    return value


def _validate_policy(policy: dict[str, Any], *, workspace_root: Path) -> None:
    schema = _require_mapping(policy, "schema", where="policy")
    required_repo_fields = schema.get("repo_entry_required_fields")
    if not isinstance(required_repo_fields, list) or not all(isinstance(x, str) for x in required_repo_fields):
        raise PolicyError("policy.schema.repo_entry_required_fields must be a list[str]")

    repo_classes = _require_mapping(policy, "repo_classes", where="policy")
    if not repo_classes:
        raise PolicyError("policy.repo_classes must not be empty")

    unknown_classes = set(repo_classes) - set(CLASS_REQUIREMENTS)
    if unknown_classes:
        raise PolicyError(f"policy.repo_classes has unknown classes: {sorted(unknown_classes)}")
    for class_name, class_spec in repo_classes.items():
        if not isinstance(class_spec, dict):
            raise PolicyError(f"policy.repo_classes.{class_name} must be a mapping")
        required_caps = class_spec.get("required_capabilities")
        if not isinstance(required_caps, dict):
            raise PolicyError(f"policy.repo_classes.{class_name}.required_capabilities must be a mapping")
        unknown = set(required_caps) - set(CAPABILITY_KEYS)
        if unknown:
            raise PolicyError(
                f"policy.repo_classes.{class_name}.required_capabilities has unknown keys: {sorted(unknown)}"
            )
        for key in CAPABILITY_KEYS:
            if key not in required_caps:
                raise PolicyError(f"policy.repo_classes.{class_name}.required_capabilities missing key {key!r}")
            if type(required_caps[key]) is not bool:
                raise PolicyError(f"policy.repo_classes.{class_name}.required_capabilities.{key} must be a boolean")
        if required_caps != dict(CLASS_REQUIREMENTS[class_name]):
            raise PolicyError(
                f"policy.repo_classes.{class_name}.required_capabilities must exactly match "
                "the versioned capability registry"
            )

    fleet = _require_mapping(policy, "fleet", where="policy")
    repos = _require_list(fleet, "repos", where="policy.fleet")

    normalized_repos: set[Path] = set()
    for idx, entry_any in enumerate(repos):
        if not isinstance(entry_any, dict):
            raise PolicyError(f"policy.fleet.repos[{idx}] must be a mapping")
        entry = entry_any
        missing = [field for field in required_repo_fields if field not in entry]
        if missing:
            raise PolicyError(f"policy.fleet.repos[{idx}] missing required fields: {', '.join(missing)}")
        cls = entry.get("class")
        if cls not in repo_classes:
            raise PolicyError(f"policy.fleet.repos[{idx}] class {cls!r} not declared in policy.repo_classes")
        caps = entry.get("capabilities")
        if not isinstance(caps, dict):
            raise PolicyError(f"policy.fleet.repos[{idx}].capabilities must be a mapping")
        unknown = set(caps) - set(CAPABILITY_KEYS)
        if unknown:
            raise PolicyError(f"policy.fleet.repos[{idx}].capabilities has unknown keys: {sorted(unknown)}")
        for key in CAPABILITY_KEYS:
            if key not in caps or type(caps[key]) is not bool:
                raise PolicyError(f"policy.fleet.repos[{idx}].capabilities.{key} must be a boolean")
        normalized, issue = normalize_policy_repo_path(workspace_root, str(entry.get("path") or ""))
        if issue is not None:
            raise PolicyError(f"policy.fleet.repos[{idx}].path invalid: {issue}")
        if normalized in normalized_repos:
            raise PolicyError(f"policy.fleet.repos[{idx}].path duplicates normalized repo: {normalized}")
        normalized_repos.add(normalized)

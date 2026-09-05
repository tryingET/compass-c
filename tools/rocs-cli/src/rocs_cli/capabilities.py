"""Closed, versioned FCOS capability and repository-class registry."""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

CAPABILITY_REGISTRY_VERSION = 1
CAPABILITY_NAMES = ("rocs_cli_vendored", "ontology_manifest", "rocs_ci_gate")

_RAW_CLASS_REQUIREMENTS = {
    "required": {"rocs_cli_vendored": True, "ontology_manifest": True, "rocs_ci_gate": True},
    "optional": {"rocs_cli_vendored": False, "ontology_manifest": False, "rocs_ci_gate": False},
    "ontology_repo": {"rocs_cli_vendored": True, "ontology_manifest": True, "rocs_ci_gate": True},
}
CLASS_REQUIREMENTS: Mapping[str, Mapping[str, bool]] = MappingProxyType(
    {name: MappingProxyType(dict(values)) for name, values in _RAW_CLASS_REQUIREMENTS.items()}
)

# Bootstrap details are part of the same closed class contract, not a second class registry.
CLASS_BOOTSTRAP: Mapping[str, Mapping[str, object]] = MappingProxyType({
    "required": MappingProxyType({"ontology_scaffold": "repo", "gate_mode": "advisory"}),
    "optional": MappingProxyType({"ontology_scaffold": "none", "gate_mode": "inventory_only"}),
    "ontology_repo": MappingProxyType({"ontology_scaffold": "ontology_repo", "gate_mode": "strict"}),
})


def class_policy(name: str) -> dict[str, object]:
    """Return a mutable complete policy, failing closed for unknown registry entries."""
    if name not in CLASS_REQUIREMENTS or name not in CLASS_BOOTSTRAP:
        raise ValueError(f"unknown repository class: {name}")
    requirements = CLASS_REQUIREMENTS[name]
    if tuple(requirements) != CAPABILITY_NAMES or any(type(v) is not bool for v in requirements.values()):
        raise ValueError(f"malformed capability registry entry: {name}")
    return {**requirements, **CLASS_BOOTSTRAP[name]}

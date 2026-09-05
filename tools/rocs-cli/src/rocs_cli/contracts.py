"""Closed, versioned, executable contract for every public CLI operation."""

from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Mapping

COMMAND_CONTRACT_VERSION = 3
EFFECT_TYPES = ("none", "artifact", "cache", "repository", "fleet", "ontology")
CONDITION_TYPES = ("always", "argument", "mode", "path-output", "runtime-feature", "authority-receipt-enabled")
AUTHORITY_ARTIFACT_TYPES = (
    "proposal-approval", "constitution-acceptance", "ontology-authority",
    "operator-approval", "transaction", "application-receipt",
)
RUNTIME_FACT_KEYS = ("index_cache_enabled", "authority_receipt_enabled")
_DECLARATION_KEYS = {"capability", "effect_rules", "required_authority_artifacts", "exit_codes"}
_RULE_KEYS = {
    "always": {"effect", "condition"},
    "argument": {"effect", "condition", "argument", "equals"},
    "mode": {"effect", "condition", "argument", "values"},
    "path-output": {"effect", "condition", "argument"},
    "runtime-feature": {"effect", "condition", "feature", "enabled"},
    "authority-receipt-enabled": {"effect", "condition"},
}


def _r(effect: str, condition: str = "always", **fields: object) -> dict[str, object]:
    return {"effect": effect, "condition": condition, **fields}


def _c(capability: str, *rules: dict[str, object], authority: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        "capability": capability,
        "effect_rules": list(rules) or [_r("none")],
        "required_authority_artifacts": list(authority),
        # argparse can return 2 and the global exception boundary can return 1.
        "exit_codes": [0, 1, 2],
    }


_CACHE = _r("cache", "runtime-feature", feature="index_cache_enabled", enabled=True)
_RAW_COMMANDS = {
    "version": _c("introspection"), "contracts": _c("introspection"),
    "discover-capabilities": _c("semantic-discovery"),
    "discover": _c("semantic-discovery"),
    "route-capabilities": _c("semantic-routing"),
    "route": _c("semantic-routing"),
    "constitution.validate": _c("constitutional-foundry"),
    "constitution.challenge": _c("constitutional-foundry"),
    "constitution.differential": _c("constitutional-foundry"),
    "constitution.mutate": _c("constitutional-foundry", authority=("constitution-acceptance",)),
    "repair-market": _c("repair-market"),
    "context.create": _c("intelligence-membrane", _r("artifact")),
    "proposal.validate": _c("intelligence-membrane"),
    "proposal.compile": _c("intelligence-membrane", _r("artifact"), authority=("proposal-approval",)),
    "transaction.prepare": _c("semantic-transaction", _r("artifact"), authority=("ontology-authority",)),
    "transaction.simulate": _c("semantic-transaction", authority=("ontology-authority", "transaction")),
    "transaction.apply": _c("semantic-transaction", _r("artifact"), _r("ontology"), authority=("ontology-authority", "operator-approval", "transaction")),
    "transaction.verify": _c("semantic-transaction", authority=("transaction", "application-receipt")),
    "transaction.rollback": _c("semantic-transaction", _r("ontology"), authority=("transaction", "application-receipt")),
    "fleet.observe": _c("fleet", _r("artifact", "path-output", argument="json"), _r("artifact", "path-output", argument="markdown")),
    "fleet.plan": _c("fleet", _r("artifact", "path-output", argument="json")),
    "fleet.apply": _c("fleet", _r("artifact", "path-output", argument="json"), _r("fleet", "argument", argument="dry_run", equals=False)),
    "fleet.run": _c("fleet", _r("artifact", "path-output", argument="json"), _r("fleet", "mode", argument="mode", values=["apply"])),
    "bootstrap": _c("repo", _r("repository", "argument", argument="dry_run", equals=False)),
    "converge": _c("repo", _r("repository", "argument", argument="dry_run", equals=False)),
    "vendor": _c("distribution", _r("artifact", "argument", argument="dry_run", equals=False)),
    "release.plan": _c("release"), "release.apply": _c("release", _r("repository")),
    "verify": _c("integrity"),
    "cleanup": _c("maintenance", _r("artifact", "argument", argument="dry_run", equals=False)),
    "doctor": _c("acceptance"), "generate": _c("generator", _r("artifact")),
    "benchmark": _c("performance", _r("artifact"), deepcopy(_CACHE)), "rules": _c("ontology"), "explain": _c("ontology"),
    "resolve": _c("ontology", _r("artifact", "argument", argument="write_dist", equals=True)),
    "summary": _c("ontology", deepcopy(_CACHE)),
    "validate": _c("ontology", _r("artifact", "authority-receipt-enabled"), deepcopy(_CACHE)),
    "diff": _c("ontology", _r("artifact"), deepcopy(_CACHE)),
    "lint": _c("ontology", deepcopy(_CACHE)),
    "check-inverses": _c("ontology", deepcopy(_CACHE), _r("ontology", "argument", argument="fix", equals=True)),
    "graph": _c("ontology", _r("artifact"), deepcopy(_CACHE)),
    "build": _c("ontology", _r("artifact"), deepcopy(_CACHE)),
    "pack": _c("ontology", deepcopy(_CACHE)), "vendored-check": _c("integrity"),
    "cache.dir": _c("cache"), "cache.ls": _c("cache"),
    "cache.clear": _c("cache", _r("cache")), "cache.prune": _c("cache", _r("cache")),
    "normalize": _c("ontology", _r("ontology", "argument", argument="apply", equals=True)),
}
_RAW_COMMANDS = dict(sorted(_RAW_COMMANDS.items()))


def _validate_registry() -> None:
    assert list(_RAW_COMMANDS) == sorted(_RAW_COMMANDS), "commands must be canonical"
    for name, declaration in _RAW_COMMANDS.items():
        assert set(declaration) == _DECLARATION_KEYS, name
        assert isinstance(declaration["capability"], str) and declaration["capability"], name
        assert declaration["exit_codes"] == sorted(set(declaration["exit_codes"])), name
        authority = declaration["required_authority_artifacts"]
        assert isinstance(authority, list) and authority == list(dict.fromkeys(authority)), name
        assert all(item in AUTHORITY_ARTIFACT_TYPES for item in authority), name
        rules = declaration["effect_rules"]
        assert isinstance(rules, list) and rules, name
        assert rules == list({repr(rule): rule for rule in rules}.values()), name
        effects = []
        for rule in rules:
            assert isinstance(rule, dict), name
            condition = rule.get("condition")
            assert condition in CONDITION_TYPES and set(rule) == _RULE_KEYS[condition], (name, rule)
            effect = rule.get("effect")
            assert effect in EFFECT_TYPES, (name, rule)
            effects.append(effect)
            if condition in {"argument", "path-output", "mode"}:
                assert isinstance(rule["argument"], str) and rule["argument"], (name, rule)
            if condition == "mode":
                assert isinstance(rule["values"], list) and rule["values"] == sorted(set(rule["values"])), (name, rule)
            if condition == "runtime-feature":
                assert rule["feature"] in RUNTIME_FACT_KEYS and isinstance(rule["enabled"], bool), (name, rule)
        assert not ("none" in effects and (len(rules) != 1 or rules[0]["condition"] != "always")), name


_validate_registry()
def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


COMMANDS: Mapping[str, Mapping[str, object]] = MappingProxyType(
    {name: _freeze(deepcopy(value)) for name, value in _RAW_COMMANDS.items()}  # type: ignore[dict-item]
)


def evaluate_effects(operation: str, arguments: Mapping[str, object], runtime_facts: Mapping[str, bool]) -> tuple[str, ...]:
    """Purely resolve a declaration using parsed arguments and explicit runtime facts."""
    if operation not in _RAW_COMMANDS:
        raise KeyError(f"unknown operation: {operation}")
    if set(runtime_facts) != set(RUNTIME_FACT_KEYS) or not all(type(v) is bool for v in runtime_facts.values()):
        raise ValueError(f"runtime_facts must be exact booleans: {RUNTIME_FACT_KEYS}")
    resolved: set[str] = set()
    for rule in _RAW_COMMANDS[operation]["effect_rules"]:
        condition = rule["condition"]
        matched = condition == "always"
        if condition == "argument":
            matched = arguments.get(str(rule["argument"])) == rule["equals"]
        elif condition == "mode":
            matched = arguments.get(str(rule["argument"])) in rule["values"]
        elif condition == "path-output":
            value = arguments.get(str(rule["argument"]))
            matched = value is not None and value != "-"
        elif condition == "runtime-feature":
            matched = runtime_facts[str(rule["feature"])] is rule["enabled"]
        elif condition == "authority-receipt-enabled":
            matched = runtime_facts["authority_receipt_enabled"]
        if matched:
            resolved.add(str(rule["effect"]))
    if resolved != {"none"}:
        resolved.discard("none")
    if not resolved:
        resolved.add("none")
    return tuple(effect for effect in EFFECT_TYPES if effect in resolved)


def command_contract() -> dict[str, object]:
    """Return a detached deterministic representation of the closed protocol."""
    return {
        "schema_version": COMMAND_CONTRACT_VERSION,
        "vocabulary": {
            "effects": list(EFFECT_TYPES), "conditions": list(CONDITION_TYPES),
            "authority_artifacts": list(AUTHORITY_ARTIFACT_TYPES), "runtime_facts": list(RUNTIME_FACT_KEYS),
        },
        "commands": {name: deepcopy(_RAW_COMMANDS[name]) for name in sorted(_RAW_COMMANDS)},
    }

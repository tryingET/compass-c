"""Bounded, local portfolio arithmetic without a cross-stakeholder objective."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction

from .core import CompassError, number, strings, text


def _object(value, field):
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise CompassError("INVALID_INPUT", f"{field} must be a plain JSON object")
    return value


def _fields(value, required, optional=(), *, field):
    _object(value, field)
    missing = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if missing or extra:
        raise CompassError(
            "INVALID_INPUT",
            f"{field}: missing {sorted(missing)}; unexpected {sorted(extra)}",
        )


def _names(value, field, maximum):
    result = strings(value, field, maximum=maximum)
    for name in result:
        text(name, field, limit=80)
    if len(set(result)) != len(result):
        raise CompassError("INVALID_INPUT", f"{field} must contain unique names")
    return result


def _quantity(value, field, *, nonnegative=False):
    return Fraction(str(number(value, field, 0 if nonnegative else -1e12, 1e12)))


def _values(value, stakeholders, field):
    _object(value, field)
    if set(value) != set(stakeholders):
        raise CompassError("INVALID_INPUT", f"{field} needs exactly one value per stakeholder")
    return [_quantity(value[name], f"{field}.{name}") for name in stakeholders]


def _dependency_layers(selected, decisions):
    """Return precedence depth, without claiming concurrent resource feasibility."""
    remaining = list(selected)
    completed = set()
    layers = []
    while remaining:
        ready = [index for index in remaining if decisions[index]["requires"] <= completed]
        if not ready:
            raise CompassError("INVALID_INPUT", "Decision dependencies contain a cycle")
        layers.append(ready)
        completed.update(ready)
        remaining = [index for index in remaining if index not in completed]
    return layers


def _model(p):
    _fields(p, ["stakeholders", "resources", "decisions"], ["source"], field="portfolio")
    stakeholders = _names(p["stakeholders"], "stakeholders", 8)
    if not stakeholders:
        raise CompassError("INVALID_INPUT", "At least one stakeholder is required")
    if "source" in p:
        text(p["source"], "source", limit=2_000)
    capacities = _object(p["resources"], "resources")
    if len(capacities) > 8:
        raise CompassError("INVALID_INPUT", "At most 8 shared resources are supported")
    resources = [text(name, "resource name", limit=80) for name in capacities]
    capacities = [
        _quantity(capacities[name], f"resources.{name}", nonnegative=True) for name in resources
    ]
    raw = p["decisions"]
    if type(raw) is not list or not 1 <= len(raw) <= 10:
        raise CompassError("INVALID_INPUT", "decisions must contain between 1 and 10 decisions")
    names = []
    for entry in raw:
        _fields(
            entry,
            ["id", "resources", "values", "defer_values"],
            ["requires", "excludes", "reversal_condition", "source"],
            field="decision",
        )
        names.append(text(entry["id"], "decision id", limit=80))
    if len(set(names)) != len(names):
        raise CompassError("INVALID_INPUT", "Decision ids must be unique")
    indices = {name: index for index, name in enumerate(names)}
    decisions = []
    for index, entry in enumerate(raw):
        usage = _object(entry["resources"], "decision resources")
        if set(usage) - set(resources):
            raise CompassError("INVALID_INPUT", "Decision resources contain an unknown resource")
        parsed = {
            "id": names[index],
            "resources": [
                _quantity(usage.get(name, 0), f"decision resources.{name}", nonnegative=True)
                for name in resources
            ],
            "values": _values(entry["values"], stakeholders, "values"),
            "defer_values": _values(entry["defer_values"], stakeholders, "defer_values"),
        }
        for field in ["requires", "excludes"]:
            links = _names(entry.get(field, []), field, 10)
            if set(links) - set(names) or names[index] in links:
                raise CompassError(
                    "INVALID_INPUT", f"{field} contains an unknown or self reference"
                )
            parsed[field] = {indices[name] for name in links}
        for field in ["source", "reversal_condition"]:
            if field in entry:
                text(entry[field], field, limit=2_000)
        decisions.append(parsed)
    # Validate the whole graph even if constraints make its cycles unselectable.
    _dependency_layers(list(range(len(decisions))), decisions)
    return stakeholders, resources, capacities, decisions


def analyze_portfolio(p: dict) -> dict:
    """Enumerate at most 1024 selections under explicitly supplied constraints.

    Each decision is either committed or deferred. Caller-supplied values are
    additive within a stakeholder, never summed across stakeholders. Capacities
    are total resource budgets, not reusable per-period scheduling capacities.
    """
    stakeholders, resources, capacities, decisions = _model(p)
    portfolios = []
    exact_values = []
    included = set()
    for mask in range(1 << len(decisions)):
        chosen = [index for index in range(len(decisions)) if mask & (1 << index)]
        chosen_set = set(chosen)
        if any(
            not decisions[index]["requires"] <= chosen_set
            or decisions[index]["excludes"] & chosen_set
            for index in chosen
        ):
            continue
        usage = [
            sum((decisions[index]["resources"][r] for index in chosen), Fraction(0))
            for r in range(len(resources))
        ]
        if any(used > capacity for used, capacity in zip(usage, capacities, strict=True)):
            continue
        deferred = [index for index in range(len(decisions)) if index not in chosen_set]
        committed_values = [
            sum((decisions[index]["values"][s] for index in chosen), Fraction(0))
            for s in range(len(stakeholders))
        ]
        deferred_values = [
            sum((decisions[index]["defer_values"][s] for index in deferred), Fraction(0))
            for s in range(len(stakeholders))
        ]
        totals = tuple(a + b for a, b in zip(committed_values, deferred_values, strict=True))
        included.update(chosen)
        exact_values.append(totals)
        portfolios.append(
            {
                "portfolio_id": f"p{mask:03x}",
                "selected": [decisions[index]["id"] for index in chosen],
                "deferred": [decisions[index]["id"] for index in deferred],
                "dependency_layers": [
                    [decisions[index]["id"] for index in layer]
                    for layer in _dependency_layers(chosen, decisions)
                ],
                "resources_used": dict(zip(resources, map(float, usage), strict=True)),
                "resources_remaining": {
                    name: float(capacity - used)
                    for name, capacity, used in zip(resources, capacities, usage, strict=True)
                },
                "committed_values": dict(
                    zip(stakeholders, map(float, committed_values), strict=True)
                ),
                "deferred_values": dict(
                    zip(stakeholders, map(float, deferred_values), strict=True)
                ),
                "stakeholder_values": dict(zip(stakeholders, map(float, totals), strict=True)),
                "stakeholder_values_exact": dict(zip(stakeholders, map(str, totals), strict=True)),
            }
        )
    # Group equal vectors before dominance comparisons, preserving every tied
    # portfolio while avoiding quadratic work for the all-equal case.
    distinct = list(dict.fromkeys(exact_values))
    nondominated = {
        candidate
        for candidate in distinct
        if not any(
            other != candidate and all(a >= b for a, b in zip(other, candidate, strict=True))
            for other in distinct
        )
    }
    ids = [row["portfolio_id"] for row in portfolios]
    optima = {}
    common = set(ids)
    for s, name in enumerate(stakeholders):
        best = max(values[s] for values in exact_values)
        winners = [pid for pid, values in zip(ids, exact_values, strict=True) if values[s] == best]
        optima[name] = winners
        common.intersection_update(winners)
    return {
        "input_model": deepcopy(p),
        "candidate_count": 1 << len(decisions),
        "feasible_count": len(portfolios),
        "feasible_portfolios": portfolios,
        "pareto_frontier": [
            pid for pid, values in zip(ids, exact_values, strict=True) if values in nondominated
        ],
        "stakeholder_optima": optima,
        "common_optima": [pid for pid in ids if pid in common],
        "preference_conflict": not bool(common),
        "unavailable_decisions": [
            decision["id"] for index, decision in enumerate(decisions) if index not in included
        ],
        "decision_assumptions": [
            {
                "id": entry["id"],
                "source": entry.get("source"),
                "reversal_condition": entry.get("reversal_condition"),
            }
            for entry in p["decisions"]
        ],
        "criterion_chosen_by_tool": False,
        "action_permission": "not_granted",
        "assumptions": [
            "The caller supplies all capacities, values, deferral values and source references; "
            "the tool does not verify that these assumptions are observed or reliable.",
            "Values are additive across decisions within each stakeholder; larger is preferable. "
            "No values are aggregated or compared across stakeholders.",
            "Deferral values explicitly model retained options or waiting costs for this horizon; "
            "unused resources do not automatically receive option value. Future learning, "
            "interactions and expiration require revised caller models.",
            "Shared resources are total budgets. Dependency layers express precedence, "
            "not a timed or concurrent resource schedule.",
            "A one-sided exclusion prohibits selecting both decisions. Dependencies require "
            "commitment to the prerequisite within the same portfolio.",
            "Pareto dominance requires no stakeholder to be worse off and at least one to be "
            "better off. All tied portfolios and stakeholder-specific optima are retained.",
            "Decimal representations of validated numbers define exact arithmetic and "
            "comparisons. Numeric output is rounded; stakeholder_values_exact preserves totals.",
            "Sources and reversal conditions are retained as caller statements, not verified "
            "evidence or guarantees that commitment can be reversed.",
        ],
        "limitations": (
            "Conditional arithmetic, not empirical validation or action authorization. "
            "Omitted constraints, nonadditive effects, uncertain input estimates, and external "
            "owners' permissions are not resolved. No portfolio or moral weights are selected."
        ),
    }

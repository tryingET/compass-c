"""Executable BDD scenarios for features/portfolio.feature."""

from __future__ import annotations

import copy
import importlib
import json
from fractions import Fraction

import pytest

from compass_c import CompassError


def analyze(model):
    return importlib.import_module("compass_c.portfolio").analyze_portfolio(model)


def decision(name, values=(1, 1), defer=(0, 0), resources=None, **extra):
    return {
        "id": name,
        "resources": {} if resources is None else resources,
        "values": dict(zip(["operator", "maintainer"], values, strict=True)),
        "defer_values": dict(zip(["operator", "maintainer"], defer, strict=True)),
        **extra,
    }


def model(decisions=None, **extra):
    return {
        "stakeholders": ["operator", "maintainer"],
        "resources": {"days": 5},
        "decisions": [decision("foundation", resources={"days": 2})]
        if decisions is None
        else decisions,
        **extra,
    }


def selected(result):
    return {tuple(row["selected"]): row for row in result["feasible_portfolios"]}


def test_shared_capacity_and_precedence_are_jointly_enforced():
    request = model(
        [
            decision("rollout", resources={"days": 3}, requires=["foundation"]),
            decision("foundation", resources={"days": 2}),
        ]
    )
    rows = selected(analyze(request))
    assert set(rows) == {(), ("foundation",), ("rollout", "foundation")}
    combined = rows[("rollout", "foundation")]
    assert combined["dependency_layers"] == [["foundation"], ["rollout"]]
    assert combined["resources_used"] == {"days": 5.0}
    assert combined["resources_remaining"] == {"days": 0.0}
    request["resources"]["days"] = 4
    assert set(selected(analyze(request))) == {(), ("foundation",)}


def test_asymmetric_exclusion_is_mutual_and_preserves_conflicting_preferences():
    result = analyze(
        model(
            [
                decision("fast", values=(9, 1), excludes=["careful"]),
                decision("careful", values=(1, 9)),
            ]
        )
    )
    rows = selected(result)
    assert set(rows) == {(), ("fast",), ("careful",)}
    fast, careful = (rows[(name,)]["portfolio_id"] for name in ["fast", "careful"])
    assert result["pareto_frontier"] == [fast, careful]
    assert result["stakeholder_optima"] == {"operator": [fast], "maintainer": [careful]}
    assert result["common_optima"] == []
    assert result["preference_conflict"] is True
    assert result["criterion_chosen_by_tool"] is False
    assert "chosen_portfolio" not in result
    assert "weighted_value" not in result


def test_caller_supplied_deferral_value_and_reversal_condition_remain_visible():
    condition = "Reconsider when the operator cannot reproduce the release smoke test."
    result = analyze(
        model([decision("release", values=(8, 1), defer=(2, 6), reversal_condition=condition)])
    )
    rows = selected(result)
    defer, commit = rows[()], rows[("release",)]
    assert defer["deferred"] == ["release"]
    assert defer["committed_values"] == {"operator": 0.0, "maintainer": 0.0}
    assert defer["deferred_values"] == {"operator": 2.0, "maintainer": 6.0}
    assert defer["stakeholder_values"] == {"operator": 2.0, "maintainer": 6.0}
    assert commit["stakeholder_values"] == {"operator": 8.0, "maintainer": 1.0}
    assert set(result["pareto_frontier"]) == {defer["portfolio_id"], commit["portfolio_id"]}
    assert result["decision_assumptions"][0]["reversal_condition"] == condition
    assumptions = " ".join(result["assumptions"]).lower()
    assert "caller" in assumptions and "deferral" in assumptions and "additive" in assumptions
    assert "schedule" in assumptions and "stakeholder" in assumptions


def test_exact_capacity_boundary_does_not_reject_decimal_sums():
    result = analyze(
        model(
            [
                decision("A", resources={"days": 0.1}),
                decision("B", resources={"days": 0.2}),
            ],
            resources={"days": 0.3},
        )
    )
    combined = selected(result)[("A", "B")]
    assert combined["resources_used"] == {"days": 0.3}
    assert combined["resources_remaining"] == {"days": 0.0}
    assert result["pareto_frontier"] == [combined["portfolio_id"]]


def test_equal_and_visually_rounded_values_do_not_erase_true_preferences():
    tied = analyze(model([decision("A", values=(0.1, 0.1)), decision("B", values=(0.2, 0.2))]))
    row = selected(tied)[("A", "B")]
    assert row["stakeholder_values_exact"] == {"operator": "3/10", "maintainer": "3/10"}
    precise = analyze(model([decision("A", values=(1, 1)), decision("B", values=(1e-20, 1e-20))]))
    rows = selected(precise)
    assert rows[("A",)]["stakeholder_values"] == rows[("A", "B")]["stakeholder_values"]
    assert precise["pareto_frontier"] == [rows[("A", "B")]["portfolio_id"]]
    assert Fraction(rows[("A", "B")]["stakeholder_values_exact"]["operator"]) > 1


def test_all_tied_feasible_portfolios_survive_and_have_common_optima():
    result = analyze(model([decision("A", values=(0, 0)), decision("B", values=(0, 0))]))
    ids = [row["portfolio_id"] for row in result["feasible_portfolios"]]
    assert len(ids) == 4
    assert result["pareto_frontier"] == ids
    assert result["stakeholder_optima"] == {"operator": ids, "maintainer": ids}
    assert result["common_optima"] == ids
    assert result["preference_conflict"] is False


def test_preserved_partial_order_does_not_invent_dependencies_between_branches():
    result = analyze(
        model(
            [
                decision("publish", requires=["test", "docs"]),
                decision("test", requires=["implement"]),
                decision("docs", requires=["implement"]),
                decision("implement"),
            ]
        )
    )
    row = selected(result)[("publish", "test", "docs", "implement")]
    assert row["dependency_layers"] == [["implement"], ["test", "docs"], ["publish"]]


def test_unavailable_choices_are_reported_and_all_deferred_is_a_real_portfolio():
    result = analyze(
        model(
            [
                decision("impossible", requires=["foundation"], excludes=["foundation"]),
                decision("foundation", resources={"days": 6}),
            ]
        )
    )
    assert list(selected(result)) == [()]
    assert result["unavailable_decisions"] == ["impossible", "foundation"]
    assert result["candidate_count"] == 4
    assert result["feasible_count"] == 1


def test_negative_values_allow_defer_to_dominate_without_authorizing_a_choice():
    result = analyze(model([decision("loss", values=(-3, -2))]))
    rows = selected(result)
    assert result["pareto_frontier"] == [rows[()]["portfolio_id"]]
    assert result["action_permission"] == "not_granted"
    assert "not empirical validation" in result["limitations"]


def test_multiple_resources_must_each_fit_and_unspecified_usage_is_zero():
    result = analyze(
        model(
            [
                decision("A", resources={"days": 3}),
                decision("B", resources={"money": 4}),
                decision("C", resources={"days": 1, "money": 2}),
            ],
            resources={"days": 4, "money": 5},
        )
    )
    rows = selected(result)
    assert ("A", "B") in rows and ("A", "C") in rows
    assert ("B", "C") not in rows and ("A", "B", "C") not in rows
    assert rows[("A",)]["resources_remaining"] == {"days": 1.0, "money": 5.0}


def test_maximum_size_is_bounded_deterministic_and_does_not_mutate_request():
    request = model([decision(f"D{i}", values=(0, 0)) for i in range(10)])
    before = copy.deepcopy(request)
    result = analyze(request)
    assert result["candidate_count"] == 1024
    assert result["feasible_count"] == 1024
    assert len(result["pareto_frontier"]) == 1024
    assert request == before
    assert analyze(request) == result
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "changes",
    [
        {"requires": ["missing"]},
        {"requires": ["foundation"]},
        {"requires": ["missing", "missing"]},
        {"requires": "foundation"},
        {"excludes": ["missing"]},
        {"excludes": ["foundation"]},
        {"resources": {"unknown": 1}},
        {"resources": {"days": -1}},
        {"resources": {"days": True}},
        {"resources": {"days": float("inf")}},
        {"resources": []},
        {"values": {"operator": 1}},
        {"values": {"operator": 1, "maintainer": 1, "third": 1}},
        {"values": {"operator": float("nan"), "maintainer": 0}},
        {"values": {"operator": True, "maintainer": 0}},
        {"defer_values": None},
        {"reversal_condition": ""},
        {"reversal_condition": "\ud800"},
        {"id": "\ud800"},
        {"id": []},
        {"unknown": 1},
    ],
)
def test_invalid_decision_fields_are_rejected(changes):
    request = model()
    request["decisions"][0].update(changes)
    with pytest.raises(CompassError) as error:
        analyze(request)
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "changes",
    [
        {"stakeholders": []},
        {"stakeholders": ["operator", "operator"]},
        {"stakeholders": [f"S{i}" for i in range(9)]},
        {"resources": {"days": -1}},
        {"resources": {"days": 1e12 + 1}},
        {"resources": {f"R{i}": 1 for i in range(9)}},
        {"decisions": []},
        {"decisions": [decision(f"D{i}") for i in range(11)]},
        {"decisions": [decision("A"), decision("A")]},
        {"decisions": [None]},
        {"weighted_value": [0.5, 0.5]},
    ],
)
def test_invalid_model_fields_and_implicit_weights_are_rejected(changes):
    with pytest.raises(CompassError) as error:
        analyze(model(**changes))
    assert error.value.code == "INVALID_INPUT"


def test_cycles_are_rejected_even_if_all_deferred_would_fit():
    with pytest.raises(CompassError, match="cycl") as error:
        analyze(
            model(
                [
                    decision("A", requires=["B"]),
                    decision("B", requires=["C"]),
                    decision("C", requires=["A"]),
                ]
            )
        )
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize("missing", ["stakeholders", "resources", "decisions"])
def test_top_level_fields_are_required(missing):
    request = model()
    del request[missing]
    with pytest.raises(CompassError) as error:
        analyze(request)
    assert error.value.code == "INVALID_INPUT"


def test_deferral_values_must_be_explicit_not_inferred_from_unused_resources():
    request = model()
    del request["decisions"][0]["defer_values"]
    with pytest.raises(CompassError) as error:
        analyze(request)
    assert error.value.code == "INVALID_INPUT"

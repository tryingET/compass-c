"""Executable BDD scenarios for features/experiments.feature."""

from __future__ import annotations

import copy
import json
from fractions import Fraction

import pytest

from compass_c import CompassError
from compass_c.experiments import propose_experiments, revise_model


def model(**overrides):
    result = {
        "actions": ["ship", "defer"],
        "scenarios": ["ready", "not ready"],
        "payoffs": [[10, -20], [0, 0]],
        "probabilities": [0.5, 0.5],
        "value_unit": "development utility points",
        "provenance": ["Author-visible development model; illustrative inputs, not host evidence."],
        "assumptions": ["Payoffs represent one bounded development decision."],
    }
    result.update(overrides)
    return result


def experiment(**overrides):
    result = {
        "id": "check",
        "question": "Does an isolated wheel round-trip succeed?",
        "protocol": "Run the supplied smoke test once in a disposable environment.",
        "outcomes": ["pass", "fail"],
        "likelihoods": [[0.8, 0.2], [0.2, 0.8]],
        "cost": 0.5,
        "duration": 10,
        "provenance": ["Owner-supplied hypothetical likelihoods, not calibrated measurements."],
        "assumptions": ["One mutually exclusive exhaustive result is observed."],
    }
    result.update(overrides)
    return result


def proposal(**overrides):
    result = {
        "model": model(),
        "experiments": [experiment()],
        "budget": 1,
        "max_duration": 20,
        "duration_unit": "minutes",
    }
    result.update(overrides)
    return result


def update(**overrides):
    result = {
        "model": model(),
        "experiment": experiment(),
        "observation": {
            "outcome": "pass",
            "source": "development/observed-smoke-result.json",
            "observed_at": "2026-09-08T01:00:00Z",
            "note": "A declared test result for this fixture, not independent host evidence.",
        },
    }
    result.update(overrides)
    return result


def test_informative_experiment_exposes_no_test_and_all_reversal_branches():
    response = propose_experiments(proposal())
    result = response["result"]
    assert result["baseline"] == {
        "expected_value": 0.0,
        "expected_value_exact": "0",
        "expected_value_winners": ["defer"],
    }
    assert result["perfect_information_value"] == 5
    assert result["decision_changing_scenarios"] == ["ready"]
    row = result["experiments"][0]
    assert row["expected_value_with_information"] == 2
    assert row["sample_information_value"] == 2
    assert row["net_information_value"] == 1.5
    assert row["expected_value_after_cost"] == 1.5
    assert row["status"] == "informative_within_bounds"
    assert row["decision_change_probability"] == 0.5
    assert row["outcomes"][0]["posterior_probabilities"] == [0.8, 0.2]
    assert row["outcomes"][0]["expected_value_winners"] == ["ship"]
    assert row["outcomes"][0]["prior_winners_rejected"] == ["defer"]
    assert row["outcomes"][1]["expected_value_winners"] == ["defer"]
    assert row["outcomes"][1]["prior_winners_rejected"] == []
    assert result["proposed_experiment_ids"] == ["check"]
    assert response["calculation"] == "experiment"
    assert response["action_permission"] == "not_granted"


def test_uncertainty_is_not_confused_with_decision_value():
    result = propose_experiments(
        proposal(model=model(payoffs=[[10, 20], [0, 0]]), experiments=[experiment(cost=0)])
    )["result"]
    assert result["perfect_information_value"] == 0
    assert result["decision_changing_scenarios"] == []
    assert result["experiments"][0]["sample_information_value"] == 0
    assert result["experiments"][0]["status"] == "no_decision_value"
    assert result["proposed_experiment_ids"] == []


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"budget": 0.49}, "over_budget"),
        ({"max_duration": 9}, "over_duration"),
        ({"experiments": [experiment(cost=2)], "budget": 3}, "net_value_not_positive"),
        ({"experiments": [experiment(likelihoods=[[0.5, 0.5], [0.5, 0.5]])]}, "no_decision_value"),
    ],
)
def test_only_positive_value_within_both_explicit_bounds_is_proposed(overrides, status):
    result = propose_experiments(proposal(**overrides))["result"]
    assert result["experiments"][0]["status"] == status
    assert result["proposed_experiment_ids"] == []


def test_equal_best_experiments_preserve_ties_and_input_order():
    result = propose_experiments(
        proposal(experiments=[experiment(id="B"), experiment(id="A"), experiment(id="C", cost=0.8)])
    )["result"]
    assert result["proposed_experiment_ids"] == ["B", "A"]
    assert result["proposal_is_sequence"] is False


def test_no_candidate_is_a_valid_no_test_result():
    result = propose_experiments(proposal(experiments=[]))["result"]
    assert result["experiments"] == []
    assert result["proposed_experiment_ids"] == []
    assert result["baseline"]["expected_value_winners"] == ["defer"]


def test_zero_probability_outcome_is_explicit_without_a_fabricated_posterior():
    row = propose_experiments(
        proposal(
            experiments=[
                experiment(
                    outcomes=["pass", "fail", "unknown"], likelihoods=[[0.8, 0.2, 0], [0.2, 0.8, 0]]
                )
            ]
        )
    )["result"]["experiments"][0]["outcomes"][2]
    assert row["outcome"] == "unknown"
    assert row["possible"] is False
    assert row["probability"] == 0
    assert row["probability_exact"] == "0"
    assert row["posterior_probabilities"] is None
    assert row["expected_value_winners"] == []


def test_tiny_positive_outcome_is_not_treated_as_impossible():
    response = propose_experiments(
        proposal(experiments=[experiment(likelihoods=[[1e-300, 1], [0, 1]], cost=0)])
    )
    branch = response["result"]["experiments"][0]["outcomes"][0]
    assert branch["possible"] is True
    assert Fraction(branch["probability_exact"]) > 0
    assert branch["posterior_probabilities"] == [1, 0]
    assert branch["expected_value_winners"] == ["ship"]
    assert response["result"]["proposed_experiment_ids"] == ["check"]


def test_decimal_ties_and_real_sub_float_differences_are_retained():
    tied = model(payoffs=[[0.1, 0.2], [0.3, 0]])
    result = propose_experiments(proposal(model=tied))["result"]
    assert result["baseline"]["expected_value_winners"] == ["ship", "defer"]
    precise = model(payoffs=[[1, 0], [1, 1e-20]])
    result = propose_experiments(proposal(model=precise))["result"]
    assert result["baseline"]["expected_value_winners"] == ["defer"]


def test_proposal_keeps_provenance_bounds_and_explicit_assumptions_without_mutation():
    parameters = proposal()
    original = copy.deepcopy(parameters)
    response = propose_experiments(parameters)
    assert parameters == original
    assert response["result"]["model"] == parameters["model"]
    assert response["result"]["experiments"][0]["experiment"] == parameters["experiments"][0]
    assert response["result"]["budget"] == 1
    assert response["result"]["max_duration"] == 20
    assert response["result"]["duration_unit"] == "minutes"
    limitations = response["limitations"].lower()
    assert "supplied" in limitations and "likelihood" in limitations
    assert "expected value" in limitations and "not empirical validation" in limitations
    assert "one" in limitations and "observation" in limitations
    assert "rounding" in limitations
    json.dumps(response, allow_nan=False)


def test_explicit_observation_updates_probabilities_preserving_the_entire_prior():
    parameters = update()
    original = copy.deepcopy(parameters)
    response = revise_model(parameters)
    result = response["result"]
    assert parameters == original
    assert result["prior_model"] == original["model"]
    assert result["model"]["probabilities"] == [0.8, 0.2]
    assert result["model"]["probabilities_exact"] == ["4/5", "1/5"]
    for field in ("provenance", "assumptions", "actions", "scenarios", "payoffs", "value_unit"):
        assert result["model"][field] == original["model"][field]
    assert result["observation"] == original["observation"]
    assert result["experiment"] == original["experiment"]
    assert result["prior_winners"] == ["defer"]
    assert result["posterior_winners"] == ["ship"]
    assert result["prior_winners_rejected"] == ["defer"]
    assert result["evidence_probability"] == 0.5
    assert result["source_verified"] is False
    assert response["calculation"] == "update_beliefs"
    assert response["action_permission"] == "not_granted"
    result["model"]["provenance"].append("mutated output")
    assert parameters == original


def test_revised_model_is_reusable_and_exact_posteriors_survive_sequential_updates():
    first = revise_model(update())["result"]["model"]
    second = revise_model(update(model=first))["result"]
    assert second["model"]["probabilities_exact"] == ["16/17", "1/17"]
    proposed = propose_experiments(proposal(model=second["model"]))["result"]
    assert proposed["baseline"]["expected_value_winners"] == ["ship"]


def test_impossible_observation_fails_without_mutating_prior():
    parameters = update(experiment=experiment(likelihoods=[[0, 1], [0, 1]]))
    original = copy.deepcopy(parameters)
    with pytest.raises(CompassError) as error:
        revise_model(parameters)
    assert error.value.code == "IMPOSSIBLE_OBSERVATION"
    assert parameters == original


@pytest.mark.parametrize(
    "overrides",
    [
        {"probabilities": None},
        {"probabilities": [1, 1]},
        {"probabilities": [True, 0]},
        {"probabilities": [float("nan"), 0]},
        {"probabilities_exact": ["3/5", "2/5"]},
        {"probabilities_exact": ["1/0", "1/2"]},
        {"probabilities_exact": ["-1/2", "3/2"]},
        {"probabilities_exact": ["1/2"]},
        {"actions": ["ship", "ship"]},
        {"actions": [str(i) for i in range(65)]},
        {"scenarios": [str(i) for i in range(129)]},
        {"payoffs": [[1, 2]]},
        {"payoffs": [[float("inf"), 0], [0, 0]]},
        {"value_unit": ""},
        {"provenance": []},
        {"assumptions": "implicit"},
        {"unknown": True},
    ],
)
def test_invalid_models_are_rejected_by_proposals_and_updates(overrides):
    for function, parameters in (
        (propose_experiments, proposal(model=model(**overrides))),
        (revise_model, update(model=model(**overrides))),
    ):
        with pytest.raises(CompassError) as error:
            function(parameters)
        assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": ""},
        {"question": ""},
        {"protocol": ""},
        {"outcomes": []},
        {"outcomes": ["same", "same"]},
        {"outcomes": [str(i) for i in range(33)]},
        {"likelihoods": [[0.8, 0.2]]},
        {"likelihoods": [[0.8, 0.8], [0.2, 0.8]]},
        {"likelihoods": [[-0.2, 1.2], [0.2, 0.8]]},
        {"likelihoods": [[True, 0], [0.2, 0.8]]},
        {"cost": -1},
        {"cost": float("inf")},
        {"duration": True},
        {"duration": -1},
        {"provenance": []},
        {"unknown": 1},
    ],
)
def test_invalid_experiments_are_rejected_by_proposals_and_updates(overrides):
    for function, parameters in (
        (propose_experiments, proposal(experiments=[experiment(**overrides)])),
        (revise_model, update(experiment=experiment(**overrides))),
    ):
        with pytest.raises(CompassError) as error:
            function(parameters)
        assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "overrides",
    [
        {"budget": -1},
        {"budget": True},
        {"max_duration": float("nan")},
        {"duration_unit": ""},
        {"experiments": [experiment(), experiment()]},
        {"experiments": [experiment(id=str(i)) for i in range(33)]},
        {"experiments": None},
        {"unbounded": True},
    ],
)
def test_proposal_limits_and_unknown_fields_are_enforced(overrides):
    with pytest.raises(CompassError) as error:
        propose_experiments(proposal(**overrides))
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "overrides",
    [
        {"outcome": "not supplied"},
        {"source": ""},
        {"observed_at": "2026-09-08"},
        {"observed_at": "2026-09-08T01:00:00"},
        {"observed_at": "not a date"},
        {"note": ""},
        {"verified": True},
    ],
)
def test_observation_requires_known_outcome_explicit_source_and_timezone(overrides):
    parameters = update()
    parameters["observation"].update(overrides)
    with pytest.raises(CompassError) as error:
        revise_model(parameters)
    assert error.value.code == "INVALID_INPUT"


def test_extreme_combined_precision_is_rejected_before_unbounded_integer_rendering():
    bounded_model = model(
        actions=["hold"],
        scenarios=[str(i) for i in range(32)],
        payoffs=[[0] * 32],
        probabilities=[1 / 32] * 32,
    )
    rare_experiment = experiment(likelihoods=[[(i + 1) * 1e-300, 1] for i in range(32)])
    for function, parameters in (
        (propose_experiments, proposal(model=bounded_model, experiments=[rare_experiment])),
        (revise_model, update(model=bounded_model, experiment=rare_experiment)),
    ):
        with pytest.raises(CompassError) as error:
            function(parameters)
        assert error.value.code == "INVALID_INPUT"
        assert "precision" in str(error.value).lower()


@pytest.mark.parametrize("exact", [["5e-1", "5e-1"], ["0.5", "0.5"]])
def test_exact_probability_grammar_rejects_exponents_before_fraction_expansion(exact):
    with pytest.raises(CompassError) as error:
        propose_experiments(proposal(model=model(probabilities_exact=exact)))
    assert error.value.code == "INVALID_INPUT"

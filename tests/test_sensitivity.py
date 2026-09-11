"""Executable BDD scenarios for features/sensitivity.feature."""

from __future__ import annotations

import copy
import json
import math
from fractions import Fraction

import pytest

from compass_c import CompassError, calculate


def parameters(**overrides):
    model = {
        "actions": ["early", "steady", "late"],
        "scenarios": ["first", "second"],
        "payoffs": [[12, 0], [9, 9], [0, 12]],
        "probability_start": [1, 0],
        "probability_end": [0, 1],
    }
    model.update(overrides)
    return model


def sensitivity(**overrides):
    return calculate("sensitivity", parameters(**overrides))["result"]


def test_three_preferences_report_exact_breakpoints_and_ties():
    result = sensitivity()
    assert [
        {key: value for key, value in point.items() if key != "t_exact"}
        for point in result["breakpoints"]
    ] == [
        {"t": 0.25, "probabilities": [0.75, 0.25], "expected_value_winners": ["early", "steady"]},
        {"t": 0.75, "probabilities": [0.25, 0.75], "expected_value_winners": ["steady", "late"]},
    ]
    assert [
        {key: value for key, value in interval.items() if not key.endswith("_exact")}
        for interval in result["intervals"]
    ] == [
        {"start": 0.0, "end": 0.25, "expected_value_winners": ["early"]},
        {"start": 0.25, "end": 0.75, "expected_value_winners": ["steady"]},
        {"start": 0.75, "end": 1.0, "expected_value_winners": ["late"]},
    ]
    assert result["rows"] == [
        {"action": "early", "expected_start": 12.0, "expected_end": 0.0},
        {"action": "steady", "expected_start": 9.0, "expected_end": 9.0},
        {"action": "late", "expected_start": 0.0, "expected_end": 12.0},
    ]
    assert result["endpoints"] == {
        "start": {
            "t": 0.0,
            "t_exact": "0",
            "probabilities": [1.0, 0.0],
            "expected_value_winners": ["early"],
        },
        "end": {
            "t": 1.0,
            "t_exact": "1",
            "probabilities": [0.0, 1.0],
            "expected_value_winners": ["late"],
        },
    }
    assert [point["t_exact"] for point in result["breakpoints"]] == ["1/4", "3/4"]


def test_advisory_result_explains_path_and_open_intervals_without_mutating_input():
    model = parameters()
    before = copy.deepcopy(model)
    response = calculate("sensitivity", model)
    result = response["result"]
    assert model == before
    assert response["calculation"] == "sensitivity"
    assert response["action_permission"] == "not_granted"
    assert result["criterion_chosen_by_tool"] is False
    assert result["probability_path"] == "p(t) = (1 - t) * probability_start + t * probability_end"
    assumptions = " ".join(result["assumptions"]).lower()
    assert "fixed" in assumptions and "payoffs" in assumptions
    assert "open" in assumptions and "interval" in assumptions
    assert "expected value" in assumptions
    assert "supplied" in assumptions and "probabilit" in assumptions
    assert "not empirical validation" in response["limitations"]
    json.dumps(response, allow_nan=False)


def test_identical_lines_keep_all_tied_actions_in_input_order():
    result = sensitivity(actions=["second", "first"], payoffs=[[7, 7], [7, 7]])
    assert result["breakpoints"] == []
    assert result["intervals"] == [
        {
            "start": 0.0,
            "end": 1.0,
            "start_exact": "0",
            "end_exact": "1",
            "expected_value_winners": ["second", "first"],
        }
    ]
    assert result["endpoints"]["start"]["expected_value_winners"] == ["second", "first"]


def test_equal_expectations_are_ties_even_when_scenario_payoffs_differ():
    result = sensitivity(
        actions=["A", "B"],
        payoffs=[[0, 10], [5, 5]],
        probability_start=[0.5, 0.5],
        probability_end=[0.5, 0.5],
    )
    assert result["breakpoints"] == []
    assert result["intervals"][0]["expected_value_winners"] == ["A", "B"]


def test_endpoint_ties_are_not_misrepresented_as_open_interval_winners():
    result = sensitivity(actions=["A", "B"], payoffs=[[1, 0], [1, 2]])
    assert result["breakpoints"] == []
    assert result["endpoints"]["start"]["expected_value_winners"] == ["A", "B"]
    assert result["endpoints"]["end"]["expected_value_winners"] == ["B"]
    assert result["intervals"][0]["expected_value_winners"] == ["B"]


def test_action_that_only_ties_at_a_breakpoint_is_preserved():
    result = sensitivity(payoffs=[[1, -1], [0, 0], [-1, 1]])
    assert result["breakpoints"][0]["expected_value_winners"] == ["early", "steady", "late"]
    assert [interval["expected_value_winners"] for interval in result["intervals"]] == [
        ["early"],
        ["late"],
    ]


def test_inferior_actions_crossing_does_not_create_a_preference_breakpoint():
    result = sensitivity(payoffs=[[100, 100], [0, 5], [5, 0]])
    assert result["breakpoints"] == []
    assert result["intervals"] == [
        {
            "start": 0.0,
            "end": 1.0,
            "start_exact": "0",
            "end_exact": "1",
            "expected_value_winners": ["early"],
        }
    ]


def test_large_payoffs_do_not_erase_small_preference_differences():
    result = sensitivity(
        actions=["A", "B"],
        payoffs=[[1e12, 1e12 - 1], [1e12 - 1, 1e12]],
    )
    assert result["endpoints"]["start"]["expected_value_winners"] == ["A"]
    assert result["endpoints"]["end"]["expected_value_winners"] == ["B"]
    assert result["breakpoints"] == [
        {
            "t": 0.5,
            "t_exact": "1/2",
            "probabilities": [0.5, 0.5],
            "expected_value_winners": ["A", "B"],
        }
    ]


def test_narrow_winning_interval_is_not_lost_to_grid_sampling_or_tolerance():
    result = sensitivity(payoffs=[[1, -1], [1e-12, 1e-12], [-1, 1]])
    assert len(result["breakpoints"]) == 2
    assert len(result["intervals"]) == 3
    center = result["intervals"][1]
    assert center["start"] < 0.5 < center["end"]
    assert center["end"] - center["start"] < 2e-12
    assert center["expected_value_winners"] == ["steady"]


def test_exact_coordinates_preserve_winning_interval_smaller_than_float_precision():
    result = sensitivity(payoffs=[[1, -1], [1e-20, 1e-20], [-1, 1]])
    assert len(result["breakpoints"]) == 2
    assert len(result["intervals"]) == 3
    center = result["intervals"][1]
    start = Fraction(center["start_exact"])
    end = Fraction(center["end_exact"])
    assert start < Fraction(1, 2) < end
    assert end - start == Fraction(1, 10**20)
    assert center["expected_value_winners"] == ["steady"]
    assert center["start"] == center["end"] == 0.5
    assert [Fraction(point["t_exact"]) for point in result["breakpoints"]] == [start, end]


def test_inferior_crossing_below_identically_tied_winners_is_not_a_breakpoint():
    result = sensitivity(
        actions=["best A", "best B", "low A", "low B"],
        payoffs=[[10, 10], [10, 10], [1, 0], [0, 1]],
    )
    assert result["breakpoints"] == []
    assert result["intervals"][0]["expected_value_winners"] == ["best A", "best B"]


def test_maximum_supported_dimensions_are_accepted():
    result = sensitivity(
        actions=[f"action {i}" for i in range(64)],
        scenarios=[f"scenario {i}" for i in range(128)],
        payoffs=[[i] * 128 for i in range(64)],
        probability_start=[1 / 128] * 128,
        probability_end=[1 / 128] * 128,
    )
    assert result["breakpoints"] == []
    assert result["intervals"][0]["expected_value_winners"] == ["action 63"]


def test_single_action_single_scenario_and_negative_payoff():
    result = sensitivity(
        actions=["only"],
        scenarios=["known"],
        payoffs=[[-3]],
        probability_start=[1],
        probability_end=[1],
    )
    assert result["breakpoints"] == []
    assert result["rows"] == [{"action": "only", "expected_start": -3.0, "expected_end": -3.0}]
    assert result["intervals"][0]["expected_value_winners"] == ["only"]


def test_reversing_probability_path_reverses_preference_intervals():
    result = sensitivity(probability_start=[0, 1], probability_end=[1, 0])
    assert [point["t"] for point in result["breakpoints"]] == [0.25, 0.75]
    assert [part["expected_value_winners"] for part in result["intervals"]] == [
        ["late"],
        ["steady"],
        ["early"],
    ]


def test_multiscenario_intervals_agree_with_independent_expected_value_calculation():
    model = parameters(
        actions=["A", "B", "C", "D"],
        scenarios=["X", "Y", "Z"],
        payoffs=[[10, -5, 0], [0, 10, 0], [0, -5, 10], [3, 3, 3]],
        probability_start=[0, 0.25, 0.75],
        probability_end=[0.75, 0.25, 0],
    )
    result = calculate("sensitivity", model)["result"]
    assert len(result["intervals"]) >= 2
    assert result["intervals"][0]["start"] == 0.0
    assert result["intervals"][-1]["end"] == 1.0
    for part in result["intervals"]:
        t = (part["start"] + part["end"]) / 2
        probabilities = [
            (1 - t) * start + t * end
            for start, end in zip(model["probability_start"], model["probability_end"], strict=True)
        ]
        values = [
            math.fsum(p * x for p, x in zip(probabilities, row, strict=True))
            for row in model["payoffs"]
        ]
        expected = [
            action
            for action, value in zip(model["actions"], values, strict=True)
            if value == max(values)
        ]
        assert part["expected_value_winners"] == expected


def test_compare_preserves_decimal_expected_value_ties_consistent_with_sensitivity():
    model = {"actions": ["A", "B"], "scenarios": ["X", "Y"], "payoffs": [[0.1, 0.2], [0.3, 0]]}
    comparison = calculate("compare", {**model, "probabilities": [0.5, 0.5]})["result"]
    assert comparison["criterion_winners"]["expected_value"] == ["A", "B"]
    assert [row["expected"] for row in comparison["rows"]] == [0.15, 0.15]
    path = sensitivity(**model, probability_start=[0.5, 0.5], probability_end=[0.5, 0.5])
    assert path["endpoints"]["start"]["expected_value_winners"] == ["A", "B"]


def test_compare_preserves_decimal_maximum_regret_ties():
    result = calculate(
        "compare",
        {
            "actions": ["A", "B"],
            "scenarios": ["X", "Y"],
            "payoffs": [[0.1, 0.4], [0.3, 0.2]],
        },
    )["result"]
    assert result["criterion_winners"]["minimax_regret"] == ["A", "B"]
    assert [row["max_regret"] for row in result["rows"]] == [0.2, 0.2]
    assert "expected_value" not in result["criterion_winners"]


def test_compare_does_not_erase_a_real_preference_when_rendered_expected_values_round_equal():
    result = calculate(
        "compare",
        {
            "actions": ["A", "B"],
            "scenarios": ["X", "Y"],
            "payoffs": [[1, 0], [1, 1e-20]],
            "probabilities": [0.5, 0.5],
        },
    )["result"]
    assert result["criterion_winners"]["expected_value"] == ["B"]
    assert [row["expected"] for row in result["rows"]] == [0.5, 0.5]


@pytest.mark.parametrize("field", ["probability_start", "probability_end"])
def test_probability_endpoints_are_required(field):
    model = parameters()
    del model[field]
    with pytest.raises(CompassError) as error:
        calculate("sensitivity", model)
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        [1],
        [1, 1],
        [-0.1, 1.1],
        [True, 0],
        [float("nan"), 0],
        [float("inf"), 0],
        ["1", 0],
        (1, 0),
    ],
)
@pytest.mark.parametrize("field", ["probability_start", "probability_end"])
def test_invalid_probability_endpoints_are_rejected(field, bad):
    with pytest.raises(CompassError) as error:
        calculate("sensitivity", parameters(**{field: bad}))
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "overrides",
    [
        {"actions": []},
        {"actions": ["A", "A", "B"]},
        {"actions": ["A"] * 65},
        {"scenarios": []},
        {"scenarios": ["X", "X"]},
        {"scenarios": ["X"] * 129},
        {"payoffs": []},
        {"payoffs": [[0], [0], [0]]},
        {"payoffs": [[True, 0], [0, 0], [0, 0]]},
        {"payoffs": [[1e12 + 1, 0], [0, 0], [0, 0]]},
        {"payoffs": [[float("nan"), 0], [0, 0], [0, 0]]},
        {"probabilities": [0.5, 0.5]},
        {"criterion": "expected_value"},
    ],
)
def test_model_validation_reuses_compare_bounds_and_rejects_implicit_criteria(overrides):
    with pytest.raises(CompassError) as error:
        calculate("sensitivity", parameters(**overrides))
    assert error.value.code == "INVALID_INPUT"

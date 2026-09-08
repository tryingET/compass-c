"""Frozen three-case arithmetic check; stdout is evidence, never action permission.

Run with the isolated installed Python, PYTHONDONTWRITEBYTECODE=1, no repository
PYTHONPATH, and a 30-second parent timeout. This script makes no external calls or
writes and launches no child process. Its oracle uses Fraction independently of
COMPASS-C. The cases are author-visible and do not prove general correctness.
"""

from __future__ import annotations

import copy
import json
import time
from datetime import UTC, datetime
from fractions import Fraction


def cases():
    return [
        {
            "name": "informative_two_state",
            "actions": ["accept", "defer"],
            "scenarios": ["ready", "defective"],
            "probabilities": [0.5, 0.5],
            "payoffs": [[10, -20], [0, 0]],
            "outcomes": ["pass", "fail"],
            "likelihoods": [[0.8, 0.2], [0.2, 0.8]],
        },
        {
            "name": "uncertainty_without_decision_value",
            "actions": ["steady", "weaker"],
            "scenarios": ["first", "second", "third"],
            "probabilities": [0.25, 0.25, 0.5],
            "payoffs": [[5, 5, 5], [1, 2, 3]],
            "outcomes": ["first_signal", "second_signal", "third_signal"],
            "likelihoods": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        },
        {
            "name": "tied_prior_and_conditional_preferences",
            "actions": ["first", "second", "hold"],
            "scenarios": ["first_state", "second_state", "third_state"],
            "probabilities": [0.25, 0.25, 0.5],
            "payoffs": [[6, -2, 0], [-2, 6, 0], [0, 0, 0]],
            "outcomes": ["first_signal", "second_signal", "third_signal"],
            "likelihoods": [[0.5, 0.25, 0.25], [0.25, 0.5, 0.25], [0.25, 0.25, 0.5]],
        },
    ]


def winners(actions, payoffs, probabilities):
    values = [
        sum(p * Fraction(str(v)) for p, v in zip(probabilities, row, strict=True))
        for row in payoffs
    ]
    best = max(values)
    return best, [name for name, value in zip(actions, values, strict=True) if value == best]


def verify_case(calculate, case, observed_at):
    actions = case["actions"]
    payoffs = case["payoffs"]
    prior = list(map(lambda value: Fraction(str(value)), case["probabilities"]))
    likelihoods = [[Fraction(str(value)) for value in row] for row in case["likelihoods"]]
    model = {
        **{key: case[key] for key in ("actions", "scenarios", "probabilities", "payoffs")},
        "value_unit": "synthetic oracle utility points",
        "provenance": ["Frozen author-visible v4-lifecycle.1 finite check input."],
        "assumptions": ["Finite synthetic model; higher utility is preferred."],
    }
    experiment = {
        "id": case["name"],
        "question": "Does this supplied signal change the finite model's preferred action?",
        "protocol": "Synthetic finite oracle case; this is not an external experiment.",
        "outcomes": case["outcomes"],
        "likelihoods": case["likelihoods"],
        "cost": 0.5,
        "duration": 1,
        "provenance": ["Frozen synthetic likelihoods, not measured test sensitivity."],
        "assumptions": ["The supplied outcomes are mutually exclusive and exhaustive."],
    }
    parameters = {
        "model": model,
        "experiments": [experiment],
        "budget": 1,
        "max_duration": 1,
        "duration_unit": "synthetic unit",
    }
    original = copy.deepcopy(parameters)
    proposal = calculate("experiment", parameters)
    assert parameters == original, "proposal mutated its input"
    assert proposal["action_permission"] == "not_granted", "proposal granted permission"
    result = proposal["result"]
    baseline, prior_winners = winners(actions, payoffs, prior)
    assert Fraction(result["baseline"]["expected_value_exact"]) == baseline
    assert result["baseline"]["expected_value_winners"] == prior_winners
    perfect = (
        sum(
            probability * max(Fraction(str(row[index])) for row in payoffs)
            for index, probability in enumerate(prior)
        )
        - baseline
    )
    assert Fraction(result["perfect_information_value_exact"]) == perfect
    informed = Fraction(0)
    martingale = [Fraction(0)] * len(prior)
    branches = result["experiments"][0]["outcomes"]
    for index, (outcome, branch) in enumerate(zip(case["outcomes"], branches, strict=True)):
        weights = [p * row[index] for p, row in zip(prior, likelihoods, strict=True)]
        chance = sum(weights)
        posterior = [weight / chance for weight in weights]
        expected, posterior_winners = winners(actions, payoffs, posterior)
        assert branch["possible"] is True
        assert branch["outcome"] == outcome
        assert Fraction(branch["probability_exact"]) == chance
        assert list(map(Fraction, branch["posterior_probabilities_exact"])) == posterior
        assert branch["expected_value_winners"] == posterior_winners
        assert Fraction(branch["expected_value_exact"]) == expected
        informed += chance * expected
        martingale = [
            previous + chance * value for previous, value in zip(martingale, posterior, strict=True)
        ]
        observation = {
            "outcome": outcome,
            "source": "synthetic-oracle://" + case["name"],
            "observed_at": observed_at,
            "note": "Synthetic case branch used for arithmetic verification only.",
        }
        update_input = {"model": model, "experiment": experiment, "observation": observation}
        update_original = copy.deepcopy(update_input)
        update = calculate("update_beliefs", update_input)
        assert update_input == update_original, "update mutated its input"
        assert update["action_permission"] == "not_granted", "update granted permission"
        revised = update["result"]
        assert revised["prior_model"] == model
        assert revised["source_verified"] is False
        assert revised["observation"] == observation
        assert revised["posterior_winners"] == posterior_winners
        assert list(map(Fraction, revised["model"]["probabilities_exact"])) == posterior
    assert martingale == prior
    sample = informed - baseline
    assert 0 <= sample <= perfect
    row = result["experiments"][0]
    assert Fraction(row["sample_information_value_exact"]) == sample
    assert Fraction(row["net_information_value_exact"]) == sample - Fraction(1, 2)
    assert result["proposed_experiment_ids"] == (
        [experiment["id"]] if sample > Fraction(1, 2) else []
    )
    return {"case": case["name"], "passed": True, "public_calculation_calls": 1 + len(branches)}


def main():
    started = datetime.now(UTC).isoformat()
    clock = time.monotonic()
    report = {
        "protocol": "v4-lifecycle.1",
        "started_at": started,
        "cases": [],
        "outcome": "fail",
        "child_processes": 0,
        "writes": 0,
        "limitations": "Three author-visible finite cases; not general correctness or authority.",
    }
    status = 1
    try:
        import compass_c

        report["installed_version"] = compass_c.VERSION
        report["installed_package_location"] = compass_c.__file__
        for case in cases():
            report["cases"].append(verify_case(compass_c.calculate, case, started))
        report["outcome"] = "pass"
        status = 0
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    report["finished_at"] = datetime.now(UTC).isoformat()
    report["elapsed_seconds"] = time.monotonic() - clock
    print(json.dumps(report, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

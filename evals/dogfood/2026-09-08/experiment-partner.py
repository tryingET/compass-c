"""Prospective development-only COMPASS-C dogfood, not host-usefulness evidence."""

import argparse
import json
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

from compass_c.experiments import propose_experiments, revise_model


def inputs():
    return {
        "model": {
            "actions": [
                "accept arithmetic implementation for integration review",
                "seek more arithmetic review",
            ],
            "scenarios": [
                "arithmetic meets tested invariants",
                "arithmetic has an invariant defect",
            ],
            "payoffs": [[10, -30], [0, 0]],
            "probabilities": [0.7, 0.3],
            "value_unit": "hypothetical development utility points",
            "provenance": [
                "Author-visible development decision model created before this invariant check."
            ],
            "assumptions": [
                "Priors and utility values are illustrative judgment, "
                "not calibrated reliability evidence."
            ],
        },
        "experiments": [
            {
                "id": "independent-finite-model-invariants",
                "question": (
                    "Do independently computed three-state Bayesian and EVSI invariants hold?"
                ),
                "protocol": (
                    "Run 32 deterministic three-state models once against an independent "
                    "exact-arithmetic oracle; stop after success or the first assertion failure."
                ),
                "outcomes": ["pass", "fail"],
                "likelihoods": [[0.95, 0.05], [0.25, 0.75]],
                "cost": 0.2,
                "duration": 30,
                "provenance": [
                    "Likelihoods, utility cost and duration bound are explicit "
                    "hypothetical development estimates."
                ],
                "assumptions": [
                    "A passing check is limited evidence for these exact invariants; "
                    "it cannot prove all software or product correctness."
                ],
            }
        ],
        "budget": 1,
        "max_duration": 30,
        "duration_unit": "seconds",
    }


def verify():
    models = 0
    for seed in range(32):
        prior = [Fraction(1, 4), Fraction(1, 4), Fraction(1, 2)]
        payoffs = [[seed % 7 - 2, 8, -4], [3, seed % 5 - 1, 3], [0, 0, 0]]
        likelihoods = [
            [Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)],
            [Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)],
            [Fraction(1, 4), Fraction(1, 4), Fraction(1, 2)],
        ]
        p = inputs()
        p["model"].update(
            actions=["A", "B", "hold"],
            scenarios=["X", "Y", "Z"],
            payoffs=payoffs,
            probabilities=[float(x) for x in prior],
        )
        p["experiments"][0].update(
            outcomes=["X-signal", "Y-signal", "Z-signal"],
            likelihoods=[[float(x) for x in row] for row in likelihoods],
        )
        actual = propose_experiments(p)["result"]
        baseline = max(sum(prior[s] * row[s] for s in range(3)) for row in payoffs)
        perfect = sum(prior[s] * max(row[s] for row in payoffs) for s in range(3)) - baseline
        informed = Fraction(0)
        martingale = [Fraction(0)] * 3
        for outcome, branch in enumerate(actual["experiments"][0]["outcomes"]):
            weights = [prior[s] * likelihoods[s][outcome] for s in range(3)]
            probability = sum(weights)
            posterior = [weight / probability for weight in weights]
            assert Fraction(branch["probability_exact"]) == probability
            assert list(map(Fraction, branch["posterior_probabilities_exact"])) == posterior
            informed += max(sum(weights[s] * row[s] for s in range(3)) for row in payoffs)
            martingale = [martingale[s] + probability * posterior[s] for s in range(3)]
        assert martingale == prior
        sample = informed - baseline
        assert 0 <= sample <= perfect
        assert Fraction(actual["perfect_information_value_exact"]) == perfect
        assert Fraction(actual["experiments"][0]["sample_information_value_exact"]) == sample
        assert Fraction(
            actual["experiments"][0]["net_information_value_exact"]
        ) == sample - Fraction(1, 5)
        models += 1
    return models


def save(path, payload):
    # Exclusive creation protects both the retained evidence and any previous rerun.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, indent=2) + "\n")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("phase", choices=["plan", "observe"])
parser.add_argument(
    "--output-dir",
    type=Path,
    required=True,
    help="Explicit directory for new evidence; existing files are never replaced.",
)
arguments = parser.parse_args()
arguments.output_dir.mkdir(parents=True, exist_ok=True)
PLAN = arguments.output_dir / "experiment-plan.json"
RESULT = arguments.output_dir / "experiment-observation.json"
REVISION = arguments.output_dir / "experiment-revision.json"
if arguments.phase == "plan":
    p = inputs()
    response = propose_experiments(p)
    save(PLAN, {"created_at": datetime.now(UTC).isoformat(), "inputs": p, "proposal": response})
    print(
        json.dumps(
            {
                "baseline": response["result"]["baseline"],
                "proposal": response["result"]["proposed_experiment_ids"],
                "net_information_value": response["result"]["experiments"][0][
                    "net_information_value"
                ],
                "plan": str(PLAN),
            }
        )
    )
elif arguments.phase == "observe":
    if RESULT.exists() or REVISION.exists():
        parser.error("Observation or revision already exists; use a fresh output directory.")
    plan = json.loads(PLAN.read_text())
    observed = {
        "outcome": "fail",
        "source": str(RESULT),
        "observed_at": datetime.now(UTC).isoformat(),
        "note": "",
    }
    try:
        count = verify()
        observed.update(
            outcome="pass",
            note=(
                "Observed all 32 independent three-state development-model checks pass "
                f"({count} completed). This tests arithmetic invariants, "
                "not independent host usefulness."
            ),
        )
    except Exception as exc:
        observed["note"] = f"Observed invariant-check failure: {type(exc).__name__}: {exc}"
    save(RESULT, observed)
    revision = revise_model(
        {
            "model": plan["inputs"]["model"],
            "experiment": plan["inputs"]["experiments"][0],
            "observation": observed,
        }
    )
    save(REVISION, revision)
    print(
        json.dumps(
            {
                "observation": observed,
                "posterior": revision["result"]["model"]["probabilities_exact"],
                "posterior_winners": revision["result"]["posterior_winners"],
                "permission": revision["action_permission"],
                "revision": str(REVISION),
            }
        )
    )

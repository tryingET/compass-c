# Bounded experiment partner

Use `calculate experiment` to examine whether a **caller-specified** experiment
could change a finite decision. Use `calculate update_beliefs` after an explicitly
sourced observation. Neither operation executes an experiment, reads the source,
writes a notebook, grants permission, or validates the model empirically.

## A complete synthetic example

The numbers below are illustrative assumptions, not measured software reliability
or host-usefulness evidence. All payoffs and costs share the named value unit.
Likelihood rows follow scenario order; columns follow outcome order.

```python
from compass_c import calculate

model = {
    "actions": ["ship", "defer"],
    "scenarios": ["ready", "not ready"],
    "payoffs": [[10, -20], [0, 0]],
    "probabilities": [0.5, 0.5],
    "value_unit": "illustrative utility points",
    "provenance": ["Synthetic author-visible example; no measured host evidence."],
    "assumptions": ["These are the only scenarios considered; higher payoff is preferable."],
}
experiment = {
    "id": "isolated-smoke-test",
    "question": "Does the isolated smoke test pass?",
    "protocol": "Run one smoke test in a disposable environment; stop after its result.",
    "outcomes": ["pass", "fail"],
    "likelihoods": [[0.8, 0.2], [0.2, 0.8]],
    "cost": 0.5,
    "duration": 10,
    "provenance": ["Synthetic likelihoods supplied for this example, not calibrated estimates."],
    "assumptions": ["The test has one mutually exclusive exhaustive outcome."],
}
proposal = calculate(
    "experiment",
    {
        "model": model,
        "experiments": [experiment],
        "budget": 1,
        "max_duration": 20,
        "duration_unit": "minutes",
    },
)
```

The no-test winner is `defer`, with expected value zero. Perfect information has
value 5. This test has sample information value 2 and net information value 1.5
after its 0.5 cost. Its hypothetical `pass` branch has probability 0.5, posterior
`[0.8, 0.2]`, and winner `ship`; its `fail` branch retains `defer`. These are
conditional arithmetic results, not an authorization to ship.

For the portable skill, pass the same JSON object to
`python <skill-dir>/scripts/compass.py calculate experiment --parameters 'JSON'`.
Programmatic callers should construct an argument list and use `json.dumps`
instead of interpolating arbitrary content into a shell command.

## Reading a proposal

| Result field | Meaning |
|---|---|
| `baseline` | Best expected payoff and all tied winners without an experiment. |
| `perfect_information_value` | Expected payoff with the scenario revealed, minus the no-test baseline. It is an upper bound under this finite model, not uncertainty magnitude. |
| `decision_changing_scenarios` | Positive-prior scenarios whose winner set differs from the baseline, including tie resolution. |
| `expected_value_with_information` | Expected best payoff after one observed result, before experiment cost. |
| `sample_information_value` | Expected value with information minus the no-test baseline. |
| `net_information_value` | Sample information value minus the supplied cost. |
| `expected_value_after_cost` | Expected value with information minus cost; compare it with the baseline. |
| `decision_change_probability` | Probability that the posterior winner set differs, including ties. |
| `prior_winners_rejected` | Baseline winners absent from a particular outcome's posterior winner set. |
| `proposed_experiment_ids` | All tied highest-net-value candidates with positive net value that meet both bounds. An empty list leaves the no-test option available. |

The output retains each experiment's protocol, provenance and assumptions. All
outcomes appear, even those of zero probability. An impossible branch has
`possible: false`, null posterior and no winners. Inspect `possible` and
`probability_exact` when floating-point display rounds a tiny probability to zero.
Numbers with `_exact` counterparts preserve rational decimal arithmetic.

Costs and durations bound each candidate individually. Candidates are alternatives:
`proposal_is_sequence` is false. Joint experiments, sequential design, conditional
dependence between experiments, ethical admissibility and hard constraints require
an explicit owner model; they are not inferred by adding independent proposals.

## Revising from an observation

Only after obtaining an actual result, call `update_beliefs` with the model and
experiment above plus the observation. This example observation is a synthetic
fixture, not a claim that the smoke test was executed:

```python
revision = calculate(
    "update_beliefs",
    {
        "model": model,
        "experiment": experiment,
        "observation": {
            "outcome": "pass",
            "source": "synthetic-example://pass-fixture",
            "observed_at": "2026-09-08T01:00:00Z",
            "note": "Synthetic demonstration observation; replace with your actual result.",
        },
    },
)
revised_model = revision["result"]["model"]
```

The result retains the entire `prior_model`, experiment and observation. Its new
`model` has posterior probabilities and `probabilities_exact` (here `4/5`, `1/5`),
and can be passed back to either operation. Preserve the full response as an
explicitly selected audit artifact if needed. Inputs are never mutated, and no
history is automatically rewritten. `source_verified: false` means that the source
was preserved but not read or authenticated.

An outcome outside the experiment is invalid input. An outcome with zero
probability under the supplied model fails with `IMPOSSIBLE_OBSERVATION`; it does
not invent a posterior or silently repair the prior. Inspect the observation,
prior and likelihoods before explicitly proposing a replacement model.

For repeated observations, likelihoods must describe the next result conditional
on the evidence already incorporated. Reusing the same likelihood matrix asserts
that it remains appropriate; it does not prove conditional independence. Do not
count the same observation twice.

## Validation and numerical bounds

Models support 1–64 actions and 1–128 scenarios. A proposal accepts 0–32 experiments;
each has 1–32 unique outcomes. Payoffs are finite in `[-1e12, 1e12]`. Costs, budgets
and durations are finite in `[0, 1e12]`; probabilities and likelihoods are in
`[0, 1]`. Every vector must sum to one within absolute rounding tolerance `1e-10`;
the supplied vector is normalized only to correct that rounding. Missing priors
and likelihoods are rejected, never estimated.

Model and experiment provenance must be nonempty string lists; assumptions must
be explicit string lists. Observation timestamps must include a timezone. Unknown
fields are rejected. Optional `probabilities_exact` must sum exactly to one and
match the displayed probabilities. Exact strings use integer or integer-fraction
notation, never decimal or exponent notation, and are limited to 1024 characters.
Their common denominator is bounded to 3400
bits, and the combined prior/likelihood denominator to 8192 bits. Excess precision
is rejected with `INVALID_INPUT` before unbounded integer rendering. Sequential
updates remain reusable within these explicit precision bounds. A posterior beyond
the reusable model bounds is rejected before an update is returned.

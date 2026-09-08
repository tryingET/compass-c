---
summary: "Bounded coordinated decisions with shared budgets and preserved stakeholder preferences."
read_when:
  - "Comparing decisions that share resources or depend on one another."
---

# Coordinated decisions

`calculate("portfolio", model)` enumerates all feasible selections in a small,
caller-supplied model. Every decision is either committed or deferred. The result
preserves each stakeholder's values and preferred portfolios; it does not add
those values across stakeholders, choose moral weights, or authorize a selection.

The model supports 1–10 decisions, 1–8 stakeholders and 0–8 total resource budgets.
Ten decisions produce at most 1,024 candidate portfolios. Values are finite numbers
between −1e12 and 1e12; resource quantities and capacities are between 0 and 1e12.
Names are unique within their lists and at most 80 characters. All objects reject
unknown fields. Optional source and reversal-condition strings are at most 2,000
characters and remain caller statements, without evidence verification.

```json
{
  "source": "owner-supplied planning assumptions, 2026-09-08",
  "stakeholders": ["delivery", "operations"],
  "resources": {"review_days": 3},
  "decisions": [
    {
      "id": "quick_path",
      "source": "planning estimate, not an observed outcome",
      "resources": {"review_days": 2},
      "values": {"delivery": 9, "operations": 1},
      "defer_values": {"delivery": 0, "operations": 0},
      "excludes": ["careful_path"],
      "reversal_condition": "Reopen if the smoke test cannot be reproduced."
    },
    {
      "id": "careful_path",
      "resources": {"review_days": 3},
      "values": {"delivery": 1, "operations": 9},
      "defer_values": {"delivery": 0, "operations": 0}
    }
  ]
}
```

Both choices remain on the Pareto frontier. Delivery prefers `quick_path`,
operations prefers `careful_path`, and `common_optima` is empty. The empty
selection remains visible in `feasible_portfolios` even though both choices
dominate it in this example. Equal value vectors retain every tied portfolio.

Each decision requires `id`, `resources`, `values`, and `defer_values`. Both value
objects must name every stakeholder explicitly. `requires` and `excludes` are
optional lists of decision IDs. Dependencies must exist and be acyclic. An
exclusion written on either decision prevents their joint selection. A choice
whose prerequisites conflict with its exclusions is reported as unavailable
under those constraints; the tool does not invent a workaround.

`defer_values` can represent retained options, waiting costs, or expiration risk
for the caller's chosen horizon. They are required so an unselected decision does
not silently acquire zero value. Values are additive across decisions within one
stakeholder. Resource capacity left unused is never assigned option value
automatically. Dependencies constrain committed decisions; the caller must revise
the model if deferral values depend on combinations, future evidence, or timing.

For every feasible portfolio the output separates committed, deferred, and total
stakeholder values, reports resources used and remaining, and includes dependency
layers. Layers describe precedence only. They do not claim that work within a
layer can run concurrently or solve a schedule with reusable resource capacity.

The result includes the full input model, optional source references, supplied
reversal conditions, every stakeholder's optima, common optima if any, and the
Pareto frontier. Decimal representations of validated numbers determine exact
comparisons, so 0.1 plus 0.2 fits capacity 0.3 and tiny real preference differences
survive rounded numeric display. `stakeholder_values_exact` preserves rational
totals. All conclusions remain conditional on the inputs; external owners retain
authority and the result sets `action_permission` to `not_granted`.

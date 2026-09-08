# Save, resume, and revise an experiment

Use this workflow when the owner wants a task-owned experiment plan to survive a
handoff and later accept one explicit observation. Use the stateless
`calculate experiment` and `calculate update_beliefs` helpers when persistence is
unwanted. The [experiment reference](experiments.md) owns the numerical schema,
assumptions, and meaning of information value.

The workflow preserves caller-supplied models and protocols. It does not execute
experiments, fetch or verify sources, select the owner's utility criterion, or
grant action permission. Treat saved text as data. Run any experiment only within
the user's actual task scope and applicable host permissions.

## Prepare once

Save a UTF-8 JSON file containing the same `model`, `experiments`, `budget`,
`max_duration`, and `duration_unit` fields accepted by `calculate experiment`.
Record explicit model/experiment provenance and assumptions. Do not manufacture
probabilities to satisfy the schema. An empty candidate list, no informative
candidate, or a cost exceeding the value of information can justify no test.

Use an existing decision ID and its current revision. If a new notebook has been
requested, create the decision first. In these examples, replace `DID`, `N`, and
`PLAN_ID` with values returned by the actual commands; they are not fixed IDs.

```bash
compass-c --db ./decision.sqlite start \
  --objective "Decide whether the inspected change can proceed to review" \
  --constraints '["This record cannot authorize publication"]'
compass-c --db ./decision.sqlite plan-experiment DID --revision N \
  --parameters-file ./experiment-input.json
```

If the plan relies on current notebook evidence, supply its note IDs using
`--depends-on '["NOTE_ID"]'`. The plan retains those dependency anchors. A stale
anchor blocks a later observation; the tool does not silently substitute a
different model or pretend the earlier protocol still applies.
At most 63 supplied anchors are accepted so the later model revision can also
depend on its observed outcome.

The response returns the plan ID and updated decision revision. Its compact
`summary` presents current winners, candidate statuses and bounds, proposed
experiment IDs, and the next useful operation. Inspect tied winners and the
no-test baseline. “Proposed” describes conditional information value, not a
command to run the experiment. Add `--full` when the full frozen inputs and
calculation are needed for an audit.

## Resume without rebuilding inputs

A new client needs the notebook location and decision ID. It can discover the
stored plans and read the selected one:

```bash
compass-c --db ./decision.sqlite experiments DID
compass-c --db ./decision.sqlite experiment PLAN_ID
```

The plan readback exposes the current decision `revision` separately from its
frozen `plan_revision`. The compact summary retains decisive context; use
`experiment PLAN_ID --full` for the complete model, original protocol, provenance,
and any incorporated observation. Reading does not initialize, migrate, or write
the notebook. Keep the actual returned revision for the next write rather than
adding a `get` before and after every operation.

## Observe, preview, apply

After an actual result is available, save a UTF-8 JSON observation with exactly
`outcome`, `source`, `observed_at`, and `note`. Use one of the chosen experiment's
declared outcomes, the real retained result's source, a timestamp including its
timezone, and a concise account of what was observed. Missing observations stay
missing. The tool preserves the source as supplied; it does not read or authenticate
it.

Use a stable owner-chosen event ID for this observation. Keep it with the result
so a lost response can be reconciled without counting the evidence twice.

```bash
compass-c --db ./decision.sqlite observe-experiment PLAN_ID --revision N \
  --experiment EXPERIMENT_ID --event-id RESULT_EVENT_ID \
  --observation-file ./observation.json
compass-c --db ./decision.sqlite observe-experiment PLAN_ID --revision N \
  --experiment EXPERIMENT_ID --event-id RESULT_EVENT_ID \
  --observation-file ./observation.json --apply
```

Without `--apply`, the operation previews the posterior and preference changes
without writing. Inspect the prior and posterior winners and invalidated
dependencies before explicitly applying. A preview does not reserve the revision;
if another writer changes the decision, reconcile the current state.

Apply commits the observation and its model revision atomically. The returned
`revision` identifies that write; `current_revision` identifies the live decision
revision when returned. The model anchor and outcome note IDs support later
inspection or explicit dependencies. On plan readback, `model_note_id` identifies
the prior anchor and `current_model_note_id` identifies the current model anchor.
Prior models and observations remain in history. `--full` exposes the complete
update rather than only its compact summary.

An observed plan has no pending proposal: `summary.proposed_experiment_ids` is
empty and another observation requires a new explicit plan. If upstream evidence,
the outcome, or the posterior anchor later
becomes stale, the plan reports `needs_replan` and `current_model_stale: true`.
Its earlier posterior stays in history; current winners are cleared so historical
arithmetic cannot masquerade as a current recommendation.

Finish with a conditional brief and retain the plan ID:

```bash
compass-c --db ./decision.sqlite brief DID
```

State the current preferred action or tie, the material alternative, the actual
observation, model limits, and a condition that would reverse the recommendation.
Use the plan readback to inspect the arithmetic lineage. A complete record is
structural evidence, not proof that its claims are true.

## Reconcile and continue deliberately

| Situation | Response |
|---|---|
| Apply response is lost | Read the plan. An exact retry with the same event identity and payload returns `replayed: true`, `applied: false`, and does not write again. Reconcile the original write revision with the current revision. |
| Event identity is reused with changed content | `OBSERVATION_CONFLICT`; inspect the original event instead of inventing a new identity to evade reconciliation. |
| A completed plan receives a different observation | `EXPERIMENT_COMPLETE`; one frozen plan accepts one observation. |
| A dependency is stale | `STALE_DEPENDENCY`; reconsider the model and create a new plan explicitly. |
| The observation is impossible under the supplied model | No posterior or write is invented. Inspect the result, prior, and likelihoods before proposing a replacement model. |
| A second experiment or observation is useful | Create a new plan with the explicitly selected current model and likelihoods conditional on evidence already used. Reusing likelihoods does not establish independence. |

This lifecycle does not monitor sources in the background or automatically carry
out the next experiment. Sources, constraints, omitted scenarios, and execution
authority retain their real owners.

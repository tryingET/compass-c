---
summary: "Standalone decision workflow, compatibility and observable failure semantics."
read_when:
  - "Creating, resuming, revising or integrating a COMPASS-C decision."
type: "reference"
---

# A decision that can change its mind

The library and CLI run locally with Python 3.11+ and no runtime dependencies.
No Agent Kernel database, model provider, external service or account is needed.
Use the skill alone for transient reasoning; save a record only within the user's scope.

## Create an inspectable brief

This example uses explicitly synthetic observations. The library returns the same
data as the CLI's `data` field. It creates only the chosen notebook.

```python
from compass_c import Notebook

book = Notebook(".compass/decisions.sqlite3")
started = book.start("Choose a pilot or delay", constraints=["Owner approval before launch"])
decision_id, revision = started["decision_id"], started["revision"]


def note(kind, content, **kwargs):
    global revision
    result = book.record(decision_id, revision, kind, content, **kwargs)
    revision = result["revision"]
    return result["note_id"]


evidence = note(
    "evidence", "Synthetic conversion is 0.12", status="observed", source="synthetic pilot run 1"
)
note("alternative", "Run a bounded pilot")
note("alternative", "Delay and gather more evidence")
note("test", "Replicate the pilot with a fresh cohort")
note("limitation", "Small synthetic cohort; no population claim", status="assumed")
note("reversal_condition", "Reconsider if conversion falls below 0.08")
note(
    "decision",
    "Prefer a bounded pilot while conversion exceeds 0.08",
    status="inferred",
    depends_on=[evidence],
)

brief = book.brief(decision_id)
assert brief["review"]["status"] == "record_complete_not_verified"
assert brief["action_permission"] == "not_granted"
```

The brief preserves note IDs, content, status, source, dependencies and timestamps.
It groups recommendations, alternatives, evidence, uncertainty, checks, effects,
reversal conditions and outcomes. Stale material is separate. Presence checks do
not establish a claim's truth, assess recommendation quality, or monitor reversal
conditions. Multiple current recommendations remain visible as disagreement.

## Correct evidence without rewriting history

```python
changed = book.revise(
    decision_id,
    revision,
    evidence,
    "Synthetic conversion is 0.04",
    "Corrected the denominator",
    status="observed",
    source="synthetic pilot run 2",
)
revision = changed["revision"]
assert evidence in changed["invalidated"]
assert book.brief(decision_id)["recommendations"] == []
history = book.get(decision_id)["revisions"]
```

Revision appends a note with the same kind and retains a replacement link and
reason. Explicit dependencies propagate invalidation transitively. All prior
decision notes are conservatively invalidated even when links were omitted.
Other undeclared dependencies still need human review. Old content is retained;
the notebook is editable local SQLite, not a tamper-proof audit log.

Record a fresh conditional recommendation only after reconsideration. Record an
`outcome` with its observed source when it resolves. A favorable outcome alone
does not establish that the decision process caused it. Use `calculate brier`
for resolved binary forecasts, preserving the original forecast and actual outcome.

## Preview and apply a batch of new observations

Several independent corrections can commit together. Preview is read-only;
apply validates the entire batch again at the same expected revision.

```python
from compass_c.evidence import apply_updates, preview_updates

current = book.brief(decision_id)
updates = [
    {
        "note_id": current["evidence"][0]["id"],
        "content": "Synthetic replicated conversion is 0.06",
        "reason": "Explicit new observation from the replica",
        "status": "observed",
        "source": "synthetic pilot run 3",
    }
]
preview = preview_updates(book, decision_id, current["revision"], updates)
assert book.get(decision_id)["revision"] == current["revision"]
committed = apply_updates(book, decision_id, current["revision"], updates)
assert committed["revision"] == current["revision"] + 1
```

The CLI equivalent is `update-evidence DECISION_ID --revision N --updates 'JSON'`;
add `--apply` to commit. MCP exposes separate `compass_preview_updates` and
`compass_apply_updates` tools. No source is fetched, and no prose reversal condition
is interpreted. Any invalid member, obsolete revision or storage failure leaves
the whole batch unchanged. Independent roots are required: update downstream
inferences explicitly after reconsidering the replacement evidence.

## Coordinate and learn without acquiring execution authority

[`calculate portfolio`](../../skills/compass/references/portfolio.md) enumerates a
bounded set of choices under shared capacity, exclusions and dependencies. It
retains each stakeholder's optima, explicit caller-supplied deferral values, and
reversal conditions. Dependency layers express precedence; they are not a schedule
or resource reservation. No common ethical scale is invented.

[`calculate experiment`](../../skills/compass/references/experiments.md) compares a
no-test baseline with supplied finite experiments, their costs, bounds, outcome
branches and expected information value. `calculate update_beliefs` consumes an
explicit sourced observation and returns the prior and updated model, exact
posterior probabilities, and conditional changes in preference. It rejects an
impossible observation or a posterior exceeding the reusable-model precision bounds.

For transient calculations, keep full models and results in task-owned JSON artifacts. Record concise computed
summaries with those source references and explicit note dependencies. When a real
result arrives, retain it as sourced evidence, revise the model explicitly, preview
the affected evidence update, then reconsider the now-stale recommendation. This
is an opt-in workflow; no monitoring, experiment execution or learning is hidden
behind a calculation.

For a persistent handoff, use the [saved experiment workflow](../../skills/compass/references/experiment-workflow.md).
`plan-experiment` freezes the model and bounded protocols in the notebook;
`experiments DECISION_ID` recovers plans; `experiment PLAN_ID` resumes one.
`observe-experiment` previews an explicitly sourced observation and `--apply`
incorporates it once, preserving prior/posterior history and invalidating dependent
reasoning. Each plan accepts one result. Replanning requires caller-supplied
likelihoods appropriate to the accumulated evidence.

## Resume and upgrade

```bash
compass-c --db .compass/decisions.sqlite3 list --limit 20 --offset 0
compass-c --db .compass/decisions.sqlite3 get DECISION_ID
compass-c --db .compass/decisions.sqlite3 brief DECISION_ID
compass-c --db .compass/decisions.sqlite3 migrate
```

`list` helps recover an ID after a lost response; it does not guarantee identity
or make a repeated write idempotent. Inspect the exact resulting record before
retrying an uncertain mutation. `REVISION_CONFLICT` means to read and reconcile.

Schema-1/2 notebooks retain their original operations. `revise` and evidence
batches need schema 2 or later; saved experiments need schema 3. `migrate`
explicitly upgrades either older schema to 3 in one transaction; reads and starting
a decision in an existing notebook never migrate. Existing
IDs, revisions, timestamps, text and invalidations survive the upgrade. A
current-schema migration is a no-op. Missing, newer, foreign, and malformed
notebooks fail closed. Back up valuable notebooks using SQLite's backup API
before upgrading; a failed migration rolls back atomically.

## Stable failure boundaries

CLI success is `{"ok": true, "data": ...}` with exit 0. Domain/input errors
are `{"ok": false, "error": {"code": ..., "message": ...}}` with exit 2;
unavailable local storage can use exit 3. Missing evaluation input files report
`INPUT_FILE_ERROR`. Reads and calculations do not create notebooks.

The portable `skills/compass/scripts/compass.py` exposes the same commands without
installing the package. MCP uses the same library through an optional installed
module. Neither interface requires the development coordination systems.

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

evidence = note("evidence", "Synthetic conversion is 0.12",
                status="observed", source="synthetic pilot run 1")
note("alternative", "Run a bounded pilot")
note("alternative", "Delay and gather more evidence")
note("test", "Replicate the pilot with a fresh cohort")
note("limitation", "Small synthetic cohort; no population claim", status="assumed")
note("reversal_condition", "Reconsider if conversion falls below 0.08")
note("decision", "Prefer a bounded pilot while conversion exceeds 0.08",
     status="inferred", depends_on=[evidence])

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
    decision_id, revision, evidence,
    "Synthetic conversion is 0.04", "Corrected the denominator",
    status="observed", source="synthetic pilot run 2",
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

Schema-1 notebooks retain their original read/write operations. `revise` requires
the explicit, transactional schema-2 upgrade; reads never migrate. Existing
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

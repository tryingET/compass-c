---
summary: "Prospective second lifecycle exercise after the original effort gate failed."
read_when:
  - "Checking the allowed correction and unchanged acceptance boundaries for run 2."
type: "reference"
---

# Run 2: remove conflicting readback guidance

The original `run-1/assessment.json` remains failed. This remediation changes
only the ordinary notebook and experiment-workflow guidance that caused extra
readbacks. It does not relax any check in `protocol.md`, its eight-operation
bound, its two discovery/resume-read bound, or its compact-response size bound.

The correction directs a preparer who needs to audit frozen inputs to request
`--full` in the initial plan write. Lifecycle response inspection can satisfy
immediate result inspection without a separate generic `get`. A resumed plan
already carries its revision. For independently requested no-write proof in an
isolated notebook, a known revision, preview revision, and unchanged complete
database/sidecar bytes avoid redundant state reads. Unknown responses, conflicts,
stale dependencies, and concurrent storage still require reconciliation.

Use two new fresh participants with the same semantic tasks and raw inputs.
The only task-file changes are the new database and evidence paths and the capture
helper filename. `capture-run-2.py` has the same capture logic as the original
helper and writes to `run-2/`. The original notebook and all original evidence
remain unchanged. The repaired guidance and all run inputs must be fingerprinted
before the new participants begin.

The installed core wheel remains byte-identical to run 1; its identity is recorded
again in the new manifest. This is a guidance remediation, not a new arithmetic
implementation. The frozen local check executes once again because the complete
fresh-client task includes recovering, executing, and recording its protocol.
Disclose that additional execution and every additional command. Repeating the
same finite check on the same artifact does not create independent reliability
evidence, and the two illustrative posteriors must not be combined.

The controller computes the same ordered eight-check assessment from new direct
evidence. Preserve any new failure without changing the rubric or coaching a
participant toward a passing command count. A pass can substantiate this bounded
workflow under the corrected guidance. It does not establish general behavioral
superiority, a comparison against the unrelated 91-command exercise, native host
discovery, or the truth of every product ambition.

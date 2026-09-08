---
summary: "Prospective installed-client protocol for a persistent experiment and cold handoff."
read_when:
  - "Preparing or assessing the first installed-client v4 lifecycle exercise."
type: "reference"
---

# Persistent experiment lifecycle: prospective local exercise

Protocol version: `v4-lifecycle.1`. This file declares an exercise, not a result.
Freeze this file, participant tasks, input files, and executable check before the
first participant runs. Record their SHA-256 hashes in the run manifest. Preserve
this version if the exercise fails; corrections require a separately identified
protocol or implementation revision and new evidence.

## Decision and direct proof

Use COMPASS-C on a real build decision: whether the installed candidate's bounded
arithmetic can proceed to integration review or needs further arithmetic repair.
The owner supplies a finite model and explicit illustrative priors, utilities,
likelihoods, cost, and duration bounds. These inputs are judgments, not measured
reliability estimates. Both candidate actions remain advisory.

The experiment is a bounded local check of the installed artifact against an
independent standard-library exact-arithmetic oracle on fixed finite inputs. The
prospective experiment input must specify the exact executable, cases, pass/fail
rule, and stopping bound. Freeze that check with the inputs. A proposal or
successful notebook operation is never the experiment's observation. The actual
check's retained output is its source; a failed or unavailable check must remain
failed or unavailable.

The user-visible outcome is a conditional brief based on that actual observation,
with the earlier model, protocol, provenance, changed preferences, and remaining
uncertainty recoverable from the notebook after a cold handoff.

## Participants and evidence boundary

Use two fresh Work Mode participants with the same available model and tool
settings, without source inspection or prior implementation/dogfood conversation.
Record settings the host exposes and mark unavailable settings unknown. The
preparer receives the installed candidate, normal skill guidance and references,
sanitized raw model/experiment input, and a new task-owned notebook path. No
expected output fixtures or grading rubric are supplied.

The resumer receives only the installed command location, notebook path, decision
ID, normal guidance, and its capture directory. It receives no transient model,
proposal output, expected posterior, or preparer's answer. It retrieves the frozen
plan from the notebook and obtains the actual observation itself. The experiment
protocol may refer to the fixed local check artifact; that artifact contains the
check inputs and assertions, not notebook responses or an expected brief.

This is author-visible local installed-client evidence. It is not a holdout,
native vendor-discovery test, external account installation, independent field
benefit study, or evidence that all consequential decisions improve. The runtime
must keep source verification and action permission separate from saved claims.

## Required checks

The reviewer assesses these ordered binary checks against retained direct
evidence. Missing or ambiguous evidence is false. The participant cannot change
the checks or declare the aggregate verdict.

| ID | Pass condition | Direct evidence |
|---|---|---|
| `installed_artifact` | Every product invocation uses the isolated installed candidate; version and package location are retained. | Manifest and exact command trace. |
| `explicit_frozen_plan` | Preparation saves the supplied model, candidates, bounds, provenance, and dependency anchors under the existing decision revision. | Input hash, prepare response, and full plan readback. |
| `cold_resume` | The second participant finds the pending plan and its protocol using only notebook path and decision ID, without reconstructing prior inputs. | Supplied task and second-participant trace. |
| `actual_observation` | A check executed after planning produces the reported outcome, source, and timestamp; no calculator/notebook success is substituted. | Check start/end, exit status, stdout/stderr, and observation input. |
| `preview_is_read_only` | Preview yields the proposed revision while database bytes and notebook revision are unchanged. | Before/after hashes and preview response. |
| `atomic_update_and_history` | Explicit apply advances one revision, retains the prior, records the observation once, and produces a recoverable posterior. | Apply response and subsequent full readback. |
| `useful_conditional_brief` | The final answer states current preferred action or tie, alternative, observation provenance, a reversal condition, and material model limits without inventing verification or authority. | Final answer and saved model lineage. |
| `bounded_effort` | The lifecycle uses at most eight product operations, at most two discovery/resume reads before preview, default workflow responses smaller than 12 KB for the frozen fixture, and no runtime source inspection. | Categorized target-command trace, UTF-8 response sizes, and participant disclosure. |

All eight checks must pass for this exercise to pass. A failed effort check does
not erase correct arithmetic, and correct arithmetic does not make the workflow
pass. There are no predeclared gaps that turn a failed required check into a pass.

The intended seven-operation path is `start`, `plan-experiment`, `experiments`,
`experiment`, observation preview, observation apply, and `brief`. A full final
plan readback is the eighth operation. Help calls and the separate experiment
execution are retained and counted separately; they do not disappear from the
reported cost. Returned IDs and revisions should support the next write without
an extra `get` before and after every operation.

The compact-output bound is 12,000 UTF-8 bytes per default plan, listing, resume,
or observation response. Explicit `--full` audit data and the generic notebook
brief are measured separately rather than silently truncated to meet that bound.

## Side effects, retries, and capture

The user has authorized local development and dogfood. Limit writes to the new
task-owned database and this run's evidence directory. Use no external accounts,
network calls, deployments, messages, purchases, or global installation. The
experiment may launch only the frozen bounded local check and its declared child
product processes. Record parent/child processes separately from product calls.

The happy path creates one decision and one plan and applies one observation.
Capture all attempted writes, failures, retries, and readbacks. An exact replay
may reconcile an uncertain apply response using the same event identity and
payload. Do not invent a new event identity to retry an unknown write outcome.
Read current state first when a response is lost; do not count reconciliations as
unobserved successful writes. Retain any departure from the eight-operation target.

Capture exact argv, exit status, stdout/stderr, and elapsed time for each launched
target process. Record capture-driver and outer host launches separately where
observable; disclose any unobserved wrapper detail rather than reconstructing it.
Save concise justifications and outputs, never private reasoning traces. Retain
the task-owned notebook locally for review and publish sanitized readbacks, not
the database. No cleanup deletes the evidence or changes an existing notebook.

## Effort and comparison

Report product operations, help requests, failures/retries, notebook readbacks,
manual JSON transfers, and elapsed time separately. Distinguish the actual
external check's cost from COMPASS-C's lifecycle overhead. Report the number and
size of caller-authored input files; a shorter command list can still conceal
substantial preparation work.

The earlier 91-command exercise is contextual evidence of friction, not this
task's baseline. It performed a different task and did not execute its proposed
experiment. Do not report a percentage improvement against it.

A later matched v0.5 comparison must freeze the same raw task, check, model,
documentation allowance, participant settings, and success conditions before
either condition runs. The baseline uses a byte-identified v0.5 installed wheel
and its ordinary calculator/notebook guidance; the candidate uses its ordinary
persisted-workflow guidance. Both preserve the same semantic outcomes. Such a
single matched exercise can describe observed task cost, not establish general
behavioral superiority. Formal skill-improvement claims require the source-owned
evaluation method, including A/A noise checks and paired evidence.

## Assessment and correction

Publish the manifest, frozen tasks/inputs/check, complete trace, concise final
brief, rubric assessment with evidence pointers, and usability findings. The
reviewer computes the aggregate as the conjunction of the eight required checks
and reports any scope or unknown-outcome issue separately.

Classify defects before changing anything: runtime, documentation, capture,
protocol, or environment. Preserve the original result. Reproduce runtime defects
with BDD and a failing test before fixing them. Rerun only affected proof under an
identified remediation; never relax this protocol after seeing results.

Method source: the current `tryingET/procesio-cli` Agent Skill Engineer 2.0.1
decision, authoring, evaluation, and field-gate references, consulted 2026-09-08.
COMPASS-C owns this bounded local exercise and its evidence; no learning promotion
or adoption by another owner follows from a pass.

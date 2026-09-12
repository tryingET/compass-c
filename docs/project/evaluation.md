---
summary: "Collect and inspect frozen paired COMPASS-C evaluation observations."
read_when:
  - "Preparing A/A or A/B host evidence or interpreting an evaluation report."
type: "reference"
---

# Paired evaluation

`compass-c evaluate` checks and summarizes observations you supply. It does not
run a model, select a skill, judge a response, or authenticate the evidence.
Passing the input checks is not proof of improved behavior or release readiness.

The repository provides two author-visible development corpora:

| Corpus | Cases | Routing contract |
| --- | ---: | --- |
| `skills/compass/evals/cases.json` | 24 | COMPASS selection and forbidden primary skill |
| `.pi/skills/compass-c-maintainer/evals/cases.json` | 8 | Expected primary skill; one unspecified owner remains unscored |

These cases are useful for development and regression detection. Renaming or
copying them does not create an independent holdout. Tests use explicitly
synthetic fixtures; they are not host evaluation results.

## Collect a matched comparison

1. Freeze the complete corpus and its rubric before collecting responses.
   Preserve the prompts, case IDs, criterion IDs, routing expectations and source
   snapshot. Compute its fingerprint using the command below.
2. Record the host, model, configuration and grader protocol. Keep these fixed
   across both arms. The configuration description should identify relevant
   sampling parameters, enabled tools and session setup; the grader description
   should identify its version and scoring procedure.
3. Collect **A/A** first: two separate complete response sets using the same
   revision. Use fresh sessions and retain both captures even when they disagree.
   A/A measures observed variability; copying responses from one arm to the other
   does not measure variability.
4. Collect **A/B** using the same fixed procedure with two distinct revision
   identifiers. Change only the intended candidate treatment. Counterbalance
   collection order and blind scoring to the arm where practical. Keep the
   collection protocol and any departures with the raw evidence.
5. Grade every response against every frozen criterion. Use JSON `true` or
   `false`, based on the retained response or execution trace. Record observed
   routing separately. Do not infer scores from a commit, test result, archive,
   intended response, or unavailable host run.
6. Supply exactly one observation per case in each arm. Pairing uses `case_id`,
   so array order does not matter. Missing cases and criteria, unknown IDs,
   duplicates and non-boolean scores fail validation. Preserve unsuccessful
   responses and regressions. If evidence cannot be graded, finish collecting
   it before producing a complete report; do not fill the gap with a guess.

Each results file represents one complete paired collection. For repeated
collections, retain separate files with their protocol and response references;
do not duplicate case IDs or treat repeated observations as independent cases.
The current command does not aggregate repeated experiments.

## Fingerprint the corpus

Run this from the repository root for the standalone corpus. Change only `path`
to use another frozen corpus.

```bash
python - <<'PY'
import hashlib
import json
from pathlib import Path

path = Path("skills/compass/evals/cases.json")
corpus = json.loads(path.read_text(encoding="utf-8"))
encoded = json.dumps(
    corpus, sort_keys=True, separators=(",", ":"),
    ensure_ascii=False, allow_nan=False,
).encode("utf-8")
print(hashlib.sha256(encoded).hexdigest())
PY
```

This is a SHA-256 digest of canonical JSON, not a hash of the file bytes. The
evaluator recomputes it and rejects a mismatch. Preserve the frozen source file
alongside the observations so the prompts and rubric remain inspectable.

## Results schema, version 1

| Field | Required value |
| --- | --- |
| `schema_version` | Integer `1` |
| `comparison` | `"A/A"` or `"A/B"` |
| `evidence_kind` | `"host_observation"` for supplied actual captures; `"synthetic_fixture"` for artificial test data |
| `corpus_sha256` | Canonical JSON fingerprint from the command above |
| `host.name` | Host identity and version |
| `host.model` | Model identity and version |
| `host.configuration` | Shared collection configuration or a stable reference to it |
| `grader` | Grader identity, version and protocol, or a stable reference to them |
| `baseline.revision`, `candidate.revision` | Identifiers of the evaluated treatment revisions; equal for A/A, distinct for A/B |
| `baseline.results`, `candidate.results` | Arrays with one result row for every frozen case |

Each result row has these fields:

| Field | Required value |
| --- | --- |
| `case_id` | Exact frozen corpus case ID |
| `compass_selected` | Boolean observation of whether COMPASS was selected |
| `primary_skill` | Observed primary skill name, or JSON `null` if there was none |
| `scores` | Object containing every criterion ID for this case, each mapped to a graded boolean |
| `response_ref` | Nonempty reference to the retained actual response or execution trace |

Text fields must be nonempty, valid UTF-8 scalar text and no longer than 12,000
characters. The evaluator accepts at most 10,000 cases and two to eight required
criteria per case. The CLI accepts input files of at most 1,000,000 characters.
References are recorded but never opened or verified by the evaluator.
`primary_skill: "compass"` requires `compass_selected: true`; contradictory
routing observations are rejected. COMPASS may be selected as a secondary skill
while a different skill remains primary.

For example, a graded `catalyst_go_no_go` row must contain exactly
`compares_options`, `states_reversal` and `separates_authority` in `scores`.
Supply the actual boolean judgments for each arm, even when they differ. No
demonstration scores are provided here to substitute for those judgments.

This minimal envelope shows where your collected rows belong. Angle-bracket
entries are placeholders, not a runnable observation file:

```text
{
  "schema_version": 1,
  "comparison": "A/B",
  "evidence_kind": "host_observation",
  "corpus_sha256": "<canonical digest>",
  "host": {
    "name": "<host and version>",
    "model": "<model and version>",
    "configuration": "<fixed collection configuration>"
  },
  "grader": "<grader and frozen scoring protocol>",
  "baseline": {
    "revision": "<baseline revision>",
    "results": [<all actual graded baseline rows>]
  },
  "candidate": {
    "revision": "<candidate revision>",
    "results": [<all actual graded candidate rows>]
  }
}
```

For each row, the shape is:

```text
{
  "case_id": "<frozen case ID>",
  "compass_selected": <observed boolean>,
  "primary_skill": <observed name or null>,
  "scores": {<every criterion ID>: <graded boolean>, ...},
  "response_ref": "<retained response reference>"
}
```

## Run and inspect

After completing `paired-results.json` from retained observations:

```bash
compass-c evaluate \
  --corpus skills/compass/evals/cases.json \
  --results paired-results.json > paired-report.json
```

The command reads both inputs and does not create or open a decision notebook.
The shell redirection above writes the report you requested. Success uses the
standard `{"ok": true, "data": ...}` envelope. Invalid evaluation contracts
produce an `INVALID_INPUT` error and exit status 2; malformed JSON and unreadable
files have their own stable input error codes.

The dependency-free Python API returns the report directly:

```python
from compass_c.evaluation import evaluate

report = evaluate(corpus, runs)  # already-loaded dictionaries; neither is mutated
```

Read `case_success`, `rubric` and `routing` together. Case success requires all
required rubric criteria and the specified routing contract. A maintainer case
with `expected_skill: null` has unspecified routing: it contributes rubric-only
case success and is excluded from routing rates. An empty routing subgroup has
`null` rates and uncertainty, not a perfect score.

`criteria` provides paired comparisons by criterion ID. `by_kind` separates
positive, negative, overlap and pressure cases. `regressions` names every
criterion or routing transition from pass to fail, including failures hidden by
an unchanged overall case score. `cases` retains individual scores, observed
routing and response references.

Each comparison reports baseline and candidate rates, their difference,
improvements, regressions, discordance and a paired standard error. Its exact
two-sided sign test conditions on discordant case pairs under a null of equally
likely improvement and regression. The overall test uses cases, not pooled
criterion scores. A/A disagreement can remain substantial when the net change
is zero.

Statistical interpretation assumes independent case pairs. Correlated cases,
subjective grading, small samples, treatment leakage or collection differences
can undermine that interpretation. Criterion and subgroup tests have no
multiple-testing correction. No significance threshold automatically establishes
benefit, authorizes release, or grants permission to act.

The report always marks provenance as unverified, behavioral improvement as
unestablished and `action_permission` as `"not_granted"`. A declared independent
holdout must use `status: "frozen_independent_holdout"`, nonempty authorship and
`split: "holdout"` for every case, but the report still cannot verify its
independence. Honest host evidence, protocol review and independent evaluation
remain necessary outside this summarizer.

## Later native Pi/GLM observations

The [2026-09-11 study](../../evals/observations/2026-09-11-glm-native/README.md)
retains 96 actual fresh-session observations with the unchanged 24-case development
corpus. A/A ran first, then counterbalanced A/B; all failures remained in the data.
Native skill acquisition and a real Pi/MCP workflow were observed. Answer-rubric
passes were 20/24 with skill versus 19/24 without it, with two improvements, one
regression and p=1.0. This does not establish reliable decision-quality improvement.
Do not interpret the larger availability/routing gain as improved reasoning.

`scripts/report_glm_dogfood.py` reuses this module's report contract. It also checks
raw-to-grade preservation, including duplicate-key lossless inspection and actual
execution overrides. Two malformed model judgments required disclosed format-only
normalization; every required judgment/evidence value was retained, without a new
model call. Raw captures remain local and are referenced by path and digest.
Neither normalization checks nor those references authenticate the original host.

The live capture drivers are archival text snapshots, not reusable commands. Their
cross-process budget ownership was not hardened; future live execution belongs behind
an execution-owner custody gate. Do not run the snapshots or infer platform-wide
budget enforcement from this controller-serialized experiment.

## Forensic review and the generated jury program

Later inspection under AK5641/evidence9198 found that the same-model grader applied
identical criteria inconsistently: both apparent improvements (t060/t059 and t076/t075)
involved missing fixtures and comparable proposed next steps graded differently.
Both timeout answers t089/t090 inferred noncommitment from missing current storage,
but only t090 failed that criterion. Eight bounded failures had empty final answers;
seven nevertheless passed the original rubric. Correct calculator outputs also
coexisted with incorrect explanations. The original counts remain historical model
judgments, not corrected or accepted quality measurements.

[The COMPASS-owned jury program](../../evals/dspx-jury/README.md) was generated using
existing DSPx, not by extending DSPx. Three independent-input `Predict` modules share
one rubric and feed a separate adjudicator alongside original evidence. The local
adapter checks criterion coverage, source quotations and explicit handling of juror
disagreement, with separate delivery/correctness/safety dimensions. Same-model
agreement remains correlated; structural validity does not prove truthful judging.

AK5673 owns the program and its completed subscription-backed diagnostic review:
eighteen GLM-5.3 juror responses and six separate GLM-5.3 adjudications. The operator
removed the erroneous metered-dollar gate; the runner uses the installed model's
131,072-token output ceiling. The initial truncated attempt remains separate.
Completed responses were carried forward without resampling through explicitly
recorded, lossless representation corrections. This is not an unchanged prospective
parser contract. No original answer or historical grade was replaced.

The [subscription review](../../evals/dspx-jury/subscription-review.md) records results,
lineage, exact readback and limitations. Original-criterion outcomes match within all
three pairs; both timeout answers fail the added effect-honesty criterion. However,
controller audit found an unsupported t075 adjudicator inference from empty tool-use
history to unavailable browsing capability, plus a focus-versus-delivery ambiguity.
These results are advisory diagnostics, not verified efficacy or trustworthy new
headline quality measurements. AK9361 records completed execution/readback; AK9362
keeps semantic-assurance failure distinct from successful transport and validation.

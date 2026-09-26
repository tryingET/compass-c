---
summary: "Actual local host observations for the frozen v0.4.0 COMPASS guidance."
read_when:
  - "Assessing what the local guidance comparison demonstrates and leaves open."
type: "reference"
---

# Local guidance diagnostic: one observed improvement, benefit unestablished

Four fresh Work Mode agent sessions produced 32 actual answers to eight frozen,
author-visible fictional tasks. A separate fresh agent graded 96 required binary
criteria with the treatment labels removed. The actual COMPASS evaluator accepted
both paired observation files and produced the retained reports.

| Comparison | Baseline cases passed | Candidate cases passed | Paired change | Improvements / regressions | Exact sign-test p |
| --- | ---: | ---: | ---: | ---: | ---: |
| A/A, guidance absent in both sessions | 7/8 | 7/8 | 0 points | 0 / 0 | 1.0 |
| A/B, absent versus manually supplied COMPASS | 7/8 | 8/8 | +12.5 percentage points | 1 / 0 | 1.0 |

The observed improvement is confined to `withdrawn_evidence`. All three
no-guidance sessions suspended the unsupported recommendation and preserved
history, but the grader judged their requests for valid or fresh evidence too
general to count as a decision-changing check. The guided answer named a
corrected, verified supplier comparison and conditions that could restore or
reverse the recommendation. No response fabricated replacement observations.

This distinction is interpretive. The grader explicitly recorded it in
`grader-results.json`; no scores were changed after grading. If general requests
for corrected evidence were accepted as the required check, all four response
sets would pass that case and the measured A/B case-success difference would be
zero. This sensitivity is a limit on the interpretation, not an alternative
unrecorded grading run.

The matched no-guidance answers contained 598 whitespace-delimited words; the
guided answers contained 683, an 85-word increase (14.2%). The longest guided
answer was 190 words, within the common 220-word limit. Greater length is a cost
observation, not a quality benefit. Routing was deliberately unscored: selection
is participant self-report and manual injection does not exercise native skill
discovery. The negative and specialist-overlap cases passed their content and
ownership criteria in all four sessions.

## Scope of the evidence

The evaluated treatment is the retained **v0.4.0** `skill-snapshot.md`, byte
SHA-256 `d24d058f60bd85e2af870e133041c0a374b9f408d346cccb1b979f2e0e60dc7c`.
The frozen source snapshot is recorded in `manifest.json`. The snapshot's relative links (`references/…`, `scripts/compass.py`) point into the original skill package, not into this directory. They are left unchanged so the bytes stay identical to the evaluated treatment. Subsequent v0.5
version or reference-link edits are not the exact bytes evaluated here, even
when the decision workflow remains unchanged. This study exercised guidance
alone; no notebook, portfolio, experiment, or MCP tool execution occurred in
the participant tasks.

The frozen corpus canonical JSON SHA-256 is
`607d16b86bed4210368f32f1356baa990ad21807953590031757ccee19ccdae1`.
Inputs were retained before collection. A/A completed before A/B. Each answer
set came from its own fresh `fork_turns="none"` context. The two A/B sessions
overlapped once a second execution slot became available. Their context and
file separation was procedural, not an enforced filesystem boundary.

The exact provider model/build, sampling parameters, and full host tool traces
were not exposed to the collector. Model/reasoning inheritance was held the
same; backend identity was not independently pinned. Storage-only compliance
and routing are self-attested. Grader labels were masked, but wording could
reveal treatment and the grader used the same host family. This is neither
proven blinding nor independent evaluation.

With eight author-visible cases, a subjective criterion, zero observed A/A
case discordance, and only one discordant A/B pair, **behavioral improvement is
not established**. The evaluator correctly retains that flag, unverified
provenance, and `action_permission: "not_granted"`. The result is enough to
replace "no actual local host observations" with inspectable local evidence.
It does not demonstrate generalized benefit, real decision outcomes, native
installation, adoption, independent holdout performance, or completed vision
horizons. No skill rewrite was made to fit this study.

## Retained evidence and reproduction

- `PROTOCOL.md`, `corpus.json`, `skill-snapshot.md`, `inputs/`: procedure, rubric,
  exact treatment and exact participant inputs frozen before collection.
- `responses/`, `manifest.json`: actual participant-written captures, hashes,
  task wrappers, collection order, identities and self-attestations.
- `grader-input.json`, `grading-key.json`, `grader-results.json`: exact masked
  grading input, separately retained label mapping, scores and rationales.
- `aa-results.json`, `ab-results.json`: complete version-1 evaluator inputs.
- `aa-report.json`, `ab-report.json`, `capture-metrics.json`: actual CLI reports
  and answer-length observations.

From the repository root, with the project CLI installed:

```bash
compass-c evaluate \
  --corpus evals/observations/2026-09-08-work-mode-guidance/corpus.json \
  --results evals/observations/2026-09-08-work-mode-guidance/aa-results.json
compass-c evaluate \
  --corpus evals/observations/2026-09-08-work-mode-guidance/corpus.json \
  --results evals/observations/2026-09-08-work-mode-guidance/ab-results.json
```

These commands reproduce the paired summaries from supplied grades. They do
not rerun the host, authenticate the captures, or independently grade answers.

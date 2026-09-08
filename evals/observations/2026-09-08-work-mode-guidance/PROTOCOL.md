---
summary: "Frozen protocol for an author-visible same-host COMPASS guidance diagnostic."
read_when:
  - "Interpreting the retained 2026-09-08 Work Mode guidance observations."
type: "reference"
---

# Protocol v1

This is a small author-visible development study, frozen before collection. It
tests whether manually supplied COMPASS guidance changes responses to eight
self-contained fictional prompts. It does not test native skill discovery,
installation, another provider, independent holdout performance, real-world
decision outcomes, or organization governance.

The operator explicitly requested dogfooding this repository in this Work Mode
session. Collection is limited to this local task and its retained evidence. The
repository's provider rider was reviewed; this record does not assert general
provider licensing or distribution compatibility. No private task data, account
credentials, notebook exports, or third-party material are included in prompts.

## Frozen procedure

1. Preserve `corpus.json`, a canonical JSON SHA-256 fingerprint, the exact
   `skills/compass/SKILL.md` source and its byte hash, and four input files before
   collecting any response. Three required binary criteria per case are fixed
   in the corpus. No criterion changes follow observation.
2. Use four fresh collaboration agents with `fork_turns="none"` and inherited
   parent model/reasoning settings. This host exposes no exact model identifier,
   host build identifier, seed, temperature, or sampling control; record them
   as unavailable rather than guessing. Same inheritance is a configuration
   control, not proof of a pinned provider backend. Participants receive the
   same task wrapper, response budget, and tool restrictions.
3. Collect A/A first in two separate no-guidance sessions. Then collect A/B in
   two further sessions, one no-guidance and one with canonical COMPASS guidance
   supplied verbatim. Randomize A/B arm order before collection. Counterbalance
   case order: ascending in the first arm of each comparison, descending in the
   second. Each participant answers all eight prompts independently; within-set
   context and order effects remain possible.
4. Each participant may read only its assigned input JSON and may write only
   its assigned response JSON. It may not read another response, corpus rubric,
   source repository, tools or references, browse, delegate, or perform actions
   described in the fictional prompts. Storage tools are allowed solely for
   the capture. Every final answer is a response to the fictional task, up to
   220 words, accompanied by a self-reported COMPASS-use boolean. The guidance
   condition may apply its supplied skill when relevant; this is manual
   injection, not host discovery.
5. Retain each exact input and participant-written response, including failed
   responses, omissions, or departures. Record actual agent IDs, order and
   tool-use attestations. Do not reconstruct unavailable runtime traces. The
   response captures are actual outputs; prompts are fictional development
   cases. Do not label the observations synthetic merely because prompts are
   fictional.
6. After all responses exist, randomize opaque labels for an arm-masked grader.
   Strip only participant labels and self-reported routing, never answer text.
   The grader receives the frozen prompts/rubric and masked answer strings,
   supplies every binary judgment with an excerpt or precise absence rationale,
   and cannot inspect input condition files or the label key. Shared filesystem
   access is procedurally restricted, not technically isolated; answer wording
   can reveal treatment. Record this as arm-masked grading, not proven blinding
   or independent evaluation. The study author does not change scores to favor
   a condition and retains any adjudication explicitly.
7. Convert completed grades and capture references into the version-1 evaluator
   schema. Use `expected_skill: null` for every case so guidance availability
   cannot mechanically create a baseline routing failure. Selection is an
   unverified participant self-report, and routing is unscored. Run the actual
   `compass-c evaluate` CLI separately for A/A and A/B and retain both reports.

## Interpretation fixed before collection

The primary diagnostic is the paired case-success change: a case passes only
when all three required criteria pass. Also inspect every criterion regression,
A/A discordance, answer length, and concrete usability defects. A/A disagreement
is a noise warning. This eight-case sample has low power, correlated prompts,
subjective binary grading, no multiplicity correction, and no independent
holdout. One favorable run cannot establish generalized or causal usefulness.
Zero measured improvement must remain zero; no skill rewrite is justified just
to make this corpus pass. Any follow-up candidate requires new retained runs.

The evaluator's provenance and improvement flags remain unverified/unestablished.
This study can close "no actual local host observations" and expose development
defects. It cannot close measured real-world benefit, independently evaluated
usefulness, user adoption, provider installation, or the whole product vision.

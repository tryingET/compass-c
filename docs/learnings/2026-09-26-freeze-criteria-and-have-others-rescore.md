---
summary: "Freeze decision criteria before probing, and have someone other than the author re-score; the author's own stale-item list was overstated in 3 of 12 cases."
read_when:
  - "You are running a rethink, retrospective or evaluation whose author also proposes the answer."
  - "You are deciding which findings need independent re-scoring."
type: "learning"
---

# Freeze the criteria, then have someone else re-score

## Context

The 2026-09-26 rethink froze its [frame](../decisions/2026-09-26-rethink-frame.md),
including populations and decision rules, before running any probe. An independent
reviewer (Pi, `openai-codex-2/gpt-6-astra`) then re-scored the author's populations
without seeing the author's report (critic A) and critiqued the argument (critic B).

## Discovery

- The blind re-score found that 3 of the author's 12 claimed stale items (P2 items 4, 11
  and 13) were not stale. The author's disputed "unit-of-record mismatch" claim was
  withdrawn.
- Because the rules were frozen, the measured guard could be judged inconclusive
  against a threshold chosen in advance, rather than one moved after seeing the result.
- The author's prior (B+C) was not supported. The owner chose the critic's
  recommendation (E*).
- The frame's counts-only privacy rule was still breached: critic packets carried five
  short prompt excerpts. Freezing the rules did not enforce them.

## Evidence

- [Probe report](../decisions/2026-09-26-rethink-probe-report.md) and its addendum.
- [`evals/rethink-2026-09-26/critique/`](../../evals/rethink-2026-09-26/critique/A-final.md):
  critic outputs A–C with run metadata.
- [Diary](../../diary/2026-09-26--decision-rethink-and-pause.md): the deviations.

## Application

Commit the criteria, with a digest, before collecting evidence. Give an independent
scorer the frozen rules and raw populations, not the author's conclusions. Check any
outgoing evidence packet mechanically against the frozen disclosure rules before
sending it.

## TIP Candidate

Yes, as a practice for owner-facing decision reviews. It is already partly implied by
the `compass` skill's falsifying checks. A TIP should add the mechanical packet check,
which this episode showed is needed.

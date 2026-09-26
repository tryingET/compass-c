---
summary: "Before choosing a mechanism, build a minimal version and measure it; the hand-scored paper version of the claim-freshness guard overstated its recall by 21–28 points."
read_when:
  - "You are choosing between candidate gates, guards or other mechanisms using replayed history."
  - "A proposal rests on a hand-assigned 'would have caught it' score."
type: "learning"
---

# Measure the mechanism, not its paper version

## Context

The 2026-09-26 rethink compared ways to keep COMPASS-C's claims fresh. Option C was a
mechanical claim-freshness guard at repository chokepoints. Its first score came from
replaying known drift and deciding by hand whether a hypothetical guard would have
caught each case.

## Discovery

The paper version scored **71%** recall and met the frozen threshold for C. The guard
as actually built caught **9/21 (43%)** on the author's populations and **9/18 (50%)**
on the independent critic's, both below the 60% rule. At HEAD it flagged 20 documents,
of which only 5 were real drift (**25% precision**). Hand scoring credited the
mechanism with judgment it did not have: which dependency mattered, and which change
to it was material.

## Evidence

- [Probe report](../decisions/2026-09-26-rethink-probe-report.md): the paper table,
  then the measured addendum.
- [`evals/rethink-2026-09-26/guard/`](../../evals/rethink-2026-09-26/guard/protocol.json):
  the archived prototype, its protocol, per-commit counts and HEAD flags.
- [`evals/rethink-2026-09-26/critique/`](../../evals/rethink-2026-09-26/critique/C-final.md):
  critic C's adjudication of the HEAD flags.

## Application

When a decision depends on how well a mechanism would perform, build the smallest real
version and run it against the same frozen populations before accepting the paper
score. Report both numbers. If building it is too expensive, treat the paper score as
an upper bound, not an estimate.

## TIP Candidate

Plausible. The lesson is not specific to COMPASS-C, but it rests on one episode. Propose
it only if a second mechanism comparison shows a similar paper-versus-measured gap.

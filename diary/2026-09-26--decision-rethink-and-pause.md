---
summary: "Deep status review, first-principles rethink with frozen probes, independent Pi critique, measured claim guard, stale-document repair and the E* pause decision."
read_when:
  - "You need the session context behind the 2026-09-26 pause decision."
type: "diary"
---

# 2026-09-26 — Rethink and pause

## What I did

- **Deep review of HEAD 23f883d.** The local suite gave 677 passed, 385 skipped and 17 subtests, matching the recorded baseline. Findings:
  - Local main is 13 commits ahead of public 92f80c6.
  - AK 5641 and 5673 were still claimed, with expired leases.
  - The company ontology is now available, and ROCS validation passes.
- **Probes of risks.** A wording-only change to `experiments._LIMITATIONS` made every saved plan, and `brief`, fail with `INVALID_STORAGE`. Stored plans are verified by recomputation.
- **Rethink.** I froze a frame (SHA `6d0f801b…`) before the revealed-preference and drift-replay probes. Probe results:
  - Five natural `SKILL.md` reads, all in Pi.
  - Zero natural notebooks.
  - A hypothetical guard scored 71% on paper.
- **Independent critique** with Pi `openai-codex-2/gpt-6-astra`, using read-only tools in isolated evidence packets:
  - **A** re-scored blind to my report and rejected three of my stale items.
  - **B** critiqued the argument and recommended E\*.
  - **C** adjudicated the guard's flags: 25% precision.
- **Measured guard.** Building it for real gave 43–50% recall.
- **Stale documents repaired** (listed in the posture), then E\* recorded in `docs/decisions/2026-09-26-adr-pause-discretionary-expansion.md`.

**Later the same day:**
- Critic outputs and the other evidence were retained in `evals/rethink-2026-09-26/`.
- AK 5673 was completed.
- Everything was published at `0526f34`; GitHub CI passed 4/4 and the publication readback passed.
- The two physical skill installs were refreshed by managed replacement (AK 10672).

## What surprised me

- The product's own build decision stopped being maintained after v0.5.0, while the operator kept rigorous COMPASS-style reasoning in AK evidence.
- Scoring a hypothetical mechanism with hand-assigned labels overstated real detection by 21–28 points.
- My own stale-item list overstated drift in 3 of 12 cases. The independent critic caught it.
- A foreground `pi -p` waits on stdin. Launch critics with `< /dev/null`.

## Deviations

- The critic packets carried five excerpts, of up to 300 characters each, of the operator's prompts in other sessions. This contradicted the frame's counts-only rule.
- Critic outputs were first kept only in session scratch space. Later the same day they were retrieved, with the guard, protocol, classifier and risk probes, into `evals/rethink-2026-09-26/`. The packets and raw event streams were not retained because they contain the prompt excerpts. The classifier export was redacted.

## Crystallization candidates

- → `docs/learnings/`: before choosing a mechanism, measure it, not only its hand-scored paper version.
- → `docs/learnings/`: freeze criteria before probes, and have someone other than the author re-score.

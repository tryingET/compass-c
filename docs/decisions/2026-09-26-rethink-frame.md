---
summary: "Frozen question, alternatives, probe procedures and decision rules for the 2026-09-26 first-principles rethink of COMPASS-C."
read_when:
  - "Interpreting the 2026-09-26 rethink probe report or continuing the rethink."
type: "reference"
status: "frozen-before-probes; proposal-stage, not an accepted decision"
---

# COMPASS-C rethink: frozen frame

This frame was written before running the probes. The session transcript records its SHA-256 before any probe command. That is procedural evidence of ordering, not cryptographic proof.

## Known contamination

The author reviewed the repository deeply earlier in the same session. Before writing this frame, the author already knew the following:

- About 13 stale claims or records. They are listed as population P2 below.
- That no decision notebook exists outside the evaluation and test workspaces under `compass-c/.compass/` and scratch space.
- The author's prior: alternative B+C wins.

The author had **not** inspected:

- Claude Code, Pi or Codex session logs for COMPASS use outside this repository.
- The drift-correction commit set (P1) selected by the procedure below.

Criteria are set so that the prior can lose (see rules R2 and R4).

## Question

Given v0.6.0, what shape should COMPASS-C take next? The owner decides. This frame grants no authority to act.

| Alt | Shape | It wins if … |
|---|---|---|
| A | Continue the current trajectory: more studies, more polish | There is natural pull (R4 positive) **and** a future independent held-out study could plausibly detect a guidance effect. The second condition is not tested here. |
| B | Narrow to a kernel: calculators plus invalidation and provenance semantics; thin guidance | Kernel pieces are used or wanted, while the notebook and guidance layers show no pull |
| C | Enforce "living decisions" at chokepoints (a CI or hook claim guard, plus AK), with notebook writes opt-in | R1 holds |
| D | Calibration ledger: forecasts with resolution dates, Brier over time | Resolvable forecasts are frequent in the owner's work. Not tested here. |
| E | Freeze v0.6.0 and archive with written-up learnings | No pull (R4 negative), the guard idea is achievable without COMPASS-C, and maintenance cost exceeds value |

Probes 2 and 3 inform only uncertainties U1–U3. They cannot decide A vs D, and they cannot tell whether guidance improves reasoning.

## Probe 2: revealed preference (U1: natural pull; U2: where living decisions live)

**Natural-use search**

- Window: 2026-09-05 (repository creation) to 2026-09-26.
- Sources:
  - `~/.claude/projects/**/*.jsonl`
  - `~/.pi/agent/sessions/**/*.jsonl`
  - `~/.codex/sessions/**/*.jsonl`
- Include a session only if its own working directory or project is outside `compass-c`, and it is not an evaluation or test harness. Exclude this session's project directory.
- A **natural invocation** is any one of:
  - a Claude `Skill` tool call with skill `compass`;
  - a read of `skills/compass/SKILL.md` or of a reference;
  - execution of `compass.py`, `compass-c` or `compass_c`;
  - a `compass_*` MCP tool call.
- Record only counts, session identifiers, dates and project names. Do not copy content.

**Natural notebooks**

- Find every SQLite file under `$HOME` that has a `compass_meta` table, then classify it as evaluation, test, demo or natural.

**Where the owner's decision reasoning for COMPASS-C actually lives**

- Count the AK evidence records attached to the COMPASS-C tasks that carry claim boundaries or remaining gaps.
- Compare that count with natural notebook decisions.

**Rule R4**

| Natural use since install | Classification |
|---|---|
| ≥3 invocations in distinct sessions, or ≥1 natural notebook | Some pull |
| 1–2 invocations | Weak or inconclusive |
| 0 | No observed pull: evidence against A as-is. This does not by itself select E. |

Absence can also mean there were no suitable decisions, or that routing failed.

## Probe 3: replay on real drift (U3: which mechanism catches stale claims)

**Population P1: drift corrections found in git**

- Take every commit whose subject matches `(?i)reconcile|align|correct|stale|refresh|bind .*posture|validate .*posture`.
- A commit counts as a drift event only if its diff changes a previously committed claim or record because later evidence made it false or incomplete.
- Record for each: the claim, the evidence change that invalidated it, and the lag (days and commits).

**Population P2: stale items found by the review, still open at HEAD**

1. Build decision `3f244e36…`: its current recommendation is still "Accept bounded v0.5.0" (`evals/dogfood/v4-lifecycle/continuing-build-record.json`).
2. `README.md` quotes the GLM result 20/24 vs 19/24 without the AK 9198 grading-invalid caveat.
3. The GLM README frames the result as "two improvements, one regression", in contrast to AK 9198.
4. `docs/project/vision-validation.md` omits the GLM study and AK 9198, and its v3 option-value row cites a dogfood whose deferral values are all zero.
5. `release.json` has `host_installation: not_performed` and a stale prior commit.
6. The blockers in `next_session_prompt.md` (AK, ontology), and its line "No snapshots currently require AK validation".
7. `final-client-exercise/manifest.json` maps v0.5.0 to `309fe48`, which is a 0.4.0 tree.
8. `governance/README.md` and `AGENTS.md` contradict each other on `work-items.json`.
9. `skills/compass/references/decision-checks.md` cites the missing `engineering/source_register.json`.
10. `docs/project/verified-publication.json` is a v0.4.0 snapshot. It is included as a control: a claim scoped with a date is **not** stale.
11. `README.md` links "dogfoods its own decisions" to the v0.5.0 `final-brief.json`.
12. `evals/dspx-jury/pilot-attempt.json` still demands a budget protocol that AK 9311 superseded.
13. The `evaluate` docstring in `scripts/compass_jury.py` still speaks of "spending".

**Mechanisms and their catch rules**

"Catch" means the mechanism signals when, or before, the evidence changes, without an agent having to remember the dependency.

- **M0: existing gates.** These are document policy, task-scope, generated drift and `validate_skill`. M0 catches an item only if one of these gates would actually fail on it.
- **M1-used: the notebook as actually used.** It catches only if both the claim and the superseding evidence were recorded as notes linked by a `depends_on` path.
- **M1-ideal: the notebook if used perfectly.** It catches if the claim is decision-shaped and the evidence could have been recorded as a note with a dependency. This is a judgment call; the rationale is recorded per item.
- **M2: a hypothetical CI claim guard.** Claim-bearing files declare evidence paths or AK evidence IDs, plus a validation date. CI fails when a declared path changes, when an AK record created after the validation date is attached to a declared task, or when a referenced path does not exist. M2 catches an item if the superseding evidence is path-detectable, AK-detectable, or a missing reference.
- **M3: skill guidance only.** This always depends on the agent recalling the dependency, so it is never a mechanical catch. It is recorded for completeness.

**Metrics**

- Catch rate per mechanism over the confirmed P1 events plus P2 items 1–9 and 11–13 (item 10 is the control).
- The actual correction lag for P1.
- The number of files M2 would need to annotate.

**Rules**

- **R1:** M2 catch rate ≥60% **and** at least twice M1-used supports C.
- **R2:** M2 catch rate <30% rejects C's premise. This is the prior's reversal condition.
- **R3:** If M1-ideal ≥ M2 while M1-used is about 0, the notebook design is adequate but not adopted. The problem is adoption or friction, not the mechanism.
- **R5:** No combination of probes 2 and 3 selects D, or answers the guidance-value question. Both stay open for probes 4 and 5 (natural-use logging, independent critique).

## Output limits

This frame and one probe report are the only outputs. No product code, commit, AK write or publication follows without the owner's decision.

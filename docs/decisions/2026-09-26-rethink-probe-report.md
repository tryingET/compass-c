---
summary: "Results of rethink probes 2 (revealed preference) and 3 (drift replay), scored against the frozen 2026-09-26 frame."
read_when:
  - "Deciding the next shape of COMPASS-C or continuing the rethink."
type: "reference"
status: "probe evidence; proposal-stage, not an accepted decision"
---

# Rethink probes 2 and 3: report

The frame is [2026-09-26-rethink-frame.md](2026-09-26-rethink-frame.md). It was frozen at SHA-256 `6d0f801b285275d6188f227861042866c7cb2bfc47d384c7d8facd02edc2f598`, 2026-09-26T08:27:42Z, before any probe ran. The same author wrote the frame and scored the probes, which is a disclosed contamination. The probes made no model calls and wrote nothing to AK or git.

## Probe 2: revealed preference

**Natural skill use** (search window 2026-09-05 to 2026-09-26)

Sources scanned:

| Host | Session files in window |
|---|---|
| Claude Code | 382 |
| Pi | 1,563 |
| Codex | 0 |

- 33 files matched an invocation pattern. 9 of those were `compass-c` sessions and were excluded.
- Of the remaining 24:
  - 9 were identical copies of one Sept 5–7 `compass-c` development session (about 186 tool calls into the repo each), so they were excluded as development.
  - 10 contained text mentions only.
  - **5 were natural invocations.** All were Pi sessions. All were a model-initiated read of `SKILL.md`, and the user never mentioned COMPASS in any of them.

| Date | Project | Trigger (paraphrased) | Routing fit |
|---|---|---|---|
| 09-11 (read 09-13) | ultimate_bug_scanner | "How to resolve further, what's the highest leverage?" | Plausible |
| 09-12 | lehrplan-viz | Build two skills with agent-skill-engineer | Overlap; specialist named explicitly |
| 09-13 | Obsidian | Design gap analysis for a state machine | Questionable ("complex" is not a trigger) |
| 09-14 | ultimate_bug_scanner | "Should we abandon our work?" | Clear go/no-go |
| 09-19 | dspx | Survey release setups and suggest options | Questionable (research) |

What happened after the read:

- No reference reads, no script, no notebook, and no MCP use.
- A keyword scan of each triggering turn's final answer found reversal or reconsideration language in **0 of 5**. One triggering turn ended with an empty final answer. This is a crude heuristic.
- Claude Code (382 sessions) had **0** natural invocations; Codex had no sessions in the window.

**Natural notebooks.** There are 195 COMPASS notebooks under `$HOME` since 2026-09-05:

- 33 in `compass-c/.compass/evaluations`;
- 158 from test runs in this session's scratch space;
- 4 from the author's own probes, which have been deleted.

**Natural notebooks: 0.**

**Where the owner's decision reasoning about COMPASS-C lives**

- There are 34 AK evidence records on the three COMPASS-C tasks: 26 pass, 5 fail and 3 skip. 20 of them carry explicit claim-boundary, remaining or limitation fields.
- AK holds 162 decisions society-wide; 0 of them concern COMPASS.
- The only self-dogfood notebook decision (`3f244e36…`) has been stale since 2026-09-08, and the notebook is not on this machine.

**R4 verdict: "some pull"** (at least 3 invocations in distinct sessions). The pull is weak in character:

- It shows up as routing into the skill, with poor precision (1–2 of 5 fit).
- There is no visible downstream effect.
- The notebook, calculators and MCP have zero natural pull.

## Probe 3: drift replay

"Catch" means the mechanism signals when, or before, the evidence changes, without an agent having to recall the dependency. The mechanisms are defined in the frame:

- **M0:** existing gates (document policy, task-scope, generated drift, `validate_skill`).
- **M1-used:** the notebook as actually used; **M1-ideal:** the notebook used perfectly.
- **M2:** a hypothetical CI claim guard.
- **M3:** skill guidance only. It always depends on the agent's recall, so it is never a mechanical catch.

### P1: confirmed drift corrections in git

13 commits matched the frozen pattern. 9 are confirmed drift corrections. The 4 excluded are 80716ca and 56066fc (additive only) and dc04e93 and d67c0ea (tests and specs, not claims).

| Commit | Stale claim → superseding evidence | Actual catcher, lag | M0 | M1-used | M1-ideal | M2 |
|---|---|---|---|---|---|---|
| 73f6c79 | v0.3 posture ("no live SDK round-trip") → v0.4 implementation | Doc policy, ≤1 day | ✓ | ✗ | ✗ | ✓ |
| 35b2007 | "Not remotely published" → publication receipt | Doc policy, same day | ✓ | ✗ | ✗ | ✓ |
| bec7f11 | v0.4 posture (ten tools, 306 tests) → v0.5 | Doc policy, ≤1 day | ✓ | ✗ | ✗ | ✓ |
| 92f80c6 | v0.5 posture → v0.6 | Doc policy, same day | ✓ | ✗ | ✗ | ✓ |
| 5e41b4f | v0.6 posture → GLM study | Doc policy, same day | ✓ | ✗ | ✗ | ✓ |
| cb3c54b | "`get` after every mutation" guidance → lifecycle returns validated state | **Dogfood run 1**, hours | ✗ | ✗ | ✗ | ✓ (noisy) |
| 9c3dc80 | AK-5641 scope snapshot → AK scope changed | Task-scope check, same day | ✓ | ✗ | ✗ | ✗ |
| 33d2c90 | AK-5641 snapshot v5 → live v7 | Task-scope check, same day | ✓ | ✗ | ✗ | ✗ |
| 91aab1a | Assumption that local main is current → origin 55 commits ahead | **Installer publication check**, about 3 days | ✗ | ✗ | ✓ | ✗ |

### P2: stale items still open at HEAD (open 14–18 days)

| # | Item | M0 | M1-used | M1-ideal | M2 (basis) |
|---|---|---|---|---|---|
| 1 | Build decision still "accept v0.5.0" | ✗ | ✗ (outcomes recorded without dependencies) | ✓ | ✓ (AK/evals) |
| 2 | README GLM score without caveat | ✗ | ✗ | ✗ | ✓ (AK 9198) |
| 3 | GLM README framing | ✗ | ✗ | ✗ | ✓ (AK 9198) |
| 4 | vision-validation omits GLM; v3 misattribution | ✗ | ✗ | ✗ | ◐ GLM part only; the misattribution was wrong from the start |
| 5 | `release.json` `host_installation` | ✗ | ✗ | ✗ | ✓ (AK 9174/9182/9183) |
| 6 | `next_session_prompt` blockers | ✗ | ✗ | ✗ | ✓ (AK 9173) |
| 7 | Manifest maps v0.5.0 to 309fe48 | ✗ | ✗ | ✗ | ✗ (wrong from the start) |
| 8 | governance README vs AGENTS | ✗ | ✗ | ✗ | ✗ (template contradiction) |
| 9 | Dangling `source_register.json` reference | ✗ | ✗ | ✗ | ✓ (missing reference) |
| 10 | *Control:* dated publication receipt | Not stale, correctly. M2 must exempt dated receipts or it produces false positives. | | | |
| 11 | README "dogfoods its own decisions" points to the v0.5 brief | ✗ | ✗ | ✗ | ✓ (path) |
| 12 | Pilot continuation still demands a budget protocol | ✗ | ✗ | ◐ | ✓ (AK 9311) |
| 13 | Jury docstring still says "spending" | ✗ | ✗ | ✗ | ✗ (code, not a claim document) |

### Totals (21 items: P1 9 plus P2 12; control excluded)

| Mechanism | Catches | Rate |
|---|---|---|
| M2, hypothetical guard (item 4 counted as caught) | 15 | **71%** |
| M0, existing gates | 7 | 33%. P1 is survivor-biased; M0 catches none of the open P2 items. |
| M1-ideal | 2–3 | 10–14% |
| M1-used | 0 | 0% |
| M3 | Never mechanical | — |

## Rule evaluation

- **R1 is met:** M2 is 71% (at least 60%) and at least twice M1-used (0). This supports C.
- **R2 is not triggered.**
- **R3 is not triggered:** M1-ideal is far below M2. This repository's drift happens mainly in *status claims across documents and records*, not in decision-shaped notes. The notebook's unit of record does not match where drift occurs, so this is not only an adoption problem.
- **R4 is "some pull", but only as imprecise routing.** The persistence and calculation layers have no pull.
- **R5:** D and the question of whether guidance improves reasoning remain open for probes 4 and 5.

## What this means for the alternatives

These are the frame's win conditions, applied to the observed results only:

| Alt | Outcome |
|---|---|
| A (continue as is) | Not supported. The notebook-centric path has no natural pull, and the guidance value is untested. |
| B (kernel) | **Not evidenced.** There was no natural use of the kernel (calculators, invalidation) either. This contradicts part of the author's prior. |
| C (chokepoint guard) | Supported on paper (R1). The cost is unmeasured: the existing posture gate alone forced 11 posture commits in 8 days, and M2 would annotate about 23 files (README, `next_session_prompt`, `release.json`, 6 `docs/project` files, 8 evals READMEs, 6 skill references, governance). It also needs dated-receipt exemptions. Such a guard generalizes `check-document-policy.sh`, so it could belong to template or engineering tooling rather than to COMPASS-C. |
| D (calibration) | Open. |
| E (freeze and archive) | Partly: the guard idea does not need COMPASS-C, but the skill does show some pull. |

**A new, cheap and testable signal: routing precision.** The skill description attracts "how to resolve", "any oversights" and "suggestions" requests, and it attracted a request that explicitly named another skill (a case the corpus itself lists as overlap). Tightening the description, then testing it against the existing negative and overlap cases, can be done independently of the rethink.

## Limits and deviations

- The same author defined the mechanisms, selected P2 (after the earlier review), and scored every item. Step 5 (an independent critique and re-scoring) is required before this informs a decision.
- M2 is hypothetical. Its catch rate is on paper; its false-positive rate and maintenance cost are unmeasured.
- n = 21. P1 is survivor-biased.
- Natural-use detection is pattern-based. Use that never reads `SKILL.md` or calls a tool is invisible to it, and Codex had no sessions in the window.
- Routing fit and the reversal-language scan are author judgment and a crude keyword heuristic.
- The frame had no "dogfood / active use" mechanism, although active use caught one P1 event (cb3c54b). The notebook also invalidated the old build decision during the actively used 2026-09-08 session, which falls outside both populations. Neither was added after the fact.

## Addendum (2026-09-26, later the same day): independent critique and the measured guard

The sections above stay unchanged as the original claims. This addendum supersedes their conclusions where the two differ.

### Setup

- **Critic runs.** Pi 0.84.4, model `openai-codex-2/gpt-6-astra` as reported by the Pi event stream (not authenticated), thinking set to high.
  - Tools were limited to `read`, `grep`, `find` and `ls`.
  - Only the provider extension (`multi-sub.ts`) was loaded. There were no skills, context files or sessions.
  - Each run worked in a separate evidence packet: the HEAD snapshot, exported commit diffs, 34 AK evidence exports, and probe-2 data.
- **Three independent runs:**
  - **A:** blind re-scoring, without this report. Packet digest `223084b3…`.
  - **B:** argument critique, with this report. Packet digest `9fec55ad…`.
  - **C:** adjudication of the guard's flags. Packet digest `d6770a6c…`.
- **Output digests:** A `db13761f…`, B `b192e58e…`, C `a1e84a93…`. The critic outputs, packets and measurement protocol were kept only in session scratch space, which is no longer available. Only these digests and the summaries below are retained.
- **Deviations:**
  - The packets included five excerpts of 300 characters or fewer from the operator's prompts in other sessions, so that routing fit could be re-scored. This contradicts the frame's "counts only" rule. Critic A flagged it.
  - The first C run stalled waiting on stdin, was stopped after about 4 minutes with no output, and was rerun.

### The guard, built and measured

The guard was built as `scripts/check-claim-freshness.py` (SHA `f0e4d4db…3dfc`). Under the [pause decision](2026-09-26-adr-pause-discretionary-expansion.md) it is archived, byte-identical, as the non-executable text file [2026-09-26-rethink-guard-prototype.py.txt](2026-09-26-rethink-guard-prototype.py.txt). Its measurement protocol (`1c87219d…da0b`) was frozen before any run on the repository.

- **Citations are extracted mechanically:** Markdown links, backticked and plain paths, `evidence_paths`, JSON path strings, and AK references.
- **It flags a document when:** a cited file changed after the document's last revision, a cited path is missing, or AK evidence on a cited task is newer than the document.

| Measure | Result |
|---|---|
| Recall, catches for the right reason (author's populations) | P1 4/9, P2 5/12. **9/21 = 43%** (paper estimate: 71%) |
| Recall (critic A's populations: P1 adds 56066fc and drops 91aab1a; P2 drops items 4, 11 and 13) | **9/18 = 50%**. The 56066fc replay is a post-hoc sensitivity check. |
| Precision at HEAD (critic C) | **5 of 20 flagged documents are real drift (25%)**. 6 of 39 reasons are signal (15%). |
| Volume | 8–20 of 33–49 in-scope documents flagged at **every** first-parent commit (median 14) |

**Why it misses:**
- Scope: evals records, dated JSON snapshots and code are excluded (6 items).
- Uncited claims: `release.json`; the publication at 35b2007; `notebook.md` before cb3c54b.
- Evidence outside the repository: the stale local baseline.
- Contradictions that exist from the start.

**Why it is noisy:**
- It treats *changed* evidence as *contradicting* evidence.
- Broad directory citations, such as `src/compass_c` or `diary`, flag unrelated changes.
- Its "missing" references point to other repositories, template placeholders, generated outputs, or paths relative to the installed skill.
- Confirming AK evidence, such as 9370, is flagged as if it contradicted the document.

**R1 and R2 applied to the measured guard:**
- R1 is **not met**: 43% and 50% are both below 60%.
- R2 is **not triggered**: both are above 30%.
- C is therefore **inconclusive**, and at 25% precision the prototype is unusable as a blocking gate.

### Independent critique: what changed

- **P2 was overstated (critic A, and C concurs on item 4).** Items 4, 11 and 13 are not stale:
  - `vision-validation.md` is an acceptance map that defers current status to the posture.
  - The dogfood link documents real historical use.
  - The docstring gives the budget to the caller, which is not wrong.
  - Item 7 has wrong provenance rather than temporal drift.
  - Critic C additionally found `evals/observations/2026-09-11-glm-native/README.md` states "The operator has not yet identified browser versus desktop versus Codex", which AK 9174 and 9197 supersede.
- **The R3 "unit-of-record mismatch" claim is withdrawn.** Critic A scored M1-ideal at 11/21, against the author's 2–3. The M1-ideal rule was judgment-dependent, and the conclusion is not robust to that disagreement.
- **The routing-precision finding is weakened.** Critic A rated the five reads as 1 clear, 3 plausible and 1 questionable; the author had 1, 1 and 3. Critic B: "an untested causal hypothesis", since the description already excludes complexity-only and specialist-owned tasks.
- **R4 is unchanged:** "some pull", weak. The zero natural notebooks are weak evidence, because the skill defaults to transient analysis (critics A and B).
- **Frame biases (critic A):**
  - P2 was chosen after the prior had formed.
  - The P1 regex overrepresents posture maintenance, and the items are not independent.
  - M1-used required real links, while M2 received hypothetical perfect declarations.
  - R1 compares against zero instead of the incremental value over M0.
  - Competing mechanisms were omitted: dogfood, review, installer verification and regression tests.
- **Critic B's recommendation (medium confidence):** E\*, a reversible freeze of discretionary expansion that preserves v0.6.0 and explicit opt-in use. Do not select C from this replay. The single most informative next observation is one naturally occurring, consequential evidence-change episode, with dependencies fixed beforehand, comparing a running guard, the AK workflow and the opt-in notebook on time to an actionable correction and on attention cost.
- **Critic B's steelman for A:** consequential decisions need portable state, lineage, atomic revision and cold handoff even when they are rare. The lifecycle dogfood and the earlier build-record invalidation are better evidence of that function than document-drift recall.

### Revised position

- **The author's prior (B+C) is not supported.** C is inconclusive when measured, and B is not evidenced.
- **Independent of the rethink, and actionable:** the confirmed drift remains real and repairable. It is in `README.md` (GLM caveat), the GLM study README, `next_session_prompt.md`, `governance/README.md`, `decision-checks.md` (missing register), `release.json` (`host_installation`) and the build record's current recommendation.
- **Still open:** probe 4 (natural-use logging) and critic B's prospective evidence-change episode.
- **Owner decision (2026-09-26):** E\*, recorded in [the pause ADR](2026-09-26-adr-pause-discretionary-expansion.md). Probe 4 and the evidence-change episode become opportunistic observations, not an active program.

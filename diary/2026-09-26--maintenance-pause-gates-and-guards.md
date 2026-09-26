---
summary: "Maintenance pass under the E* pause: calculation-kind error fix, released-plan, default-notebook and cross-process guards, gate alignment, docs, first crystallized learnings."
read_when:
  - "You need the context behind the 2026-09-26 maintenance commits after the E* decision."
  - "You are about to change experiment output, notebook defaults, CI gates or the pinned jury code."
type: "diary"
---

# 2026-09-26 — Maintenance under the pause

## Scope

The owner asked for the open items to be worked through until finished, verified and
validated. Only maintenance allowed by the
[E* decision](../docs/decisions/2026-09-26-adr-pause-discretionary-expansion.md) was
in scope: correctness, compatibility, documentation accuracy and gates. There was no
new feature, study, provider call, un-deferral of AK 5641, or release.

The starting point was verified first. Local and public `main` were both `d6eeb37`, and
GitHub CI run 36257979461 passed 4/4. AK 5641 was listed as `pending`, carrying the
active manual deferral 432; that is how `ak` shows a deferral. AK 5673 was done.

## What I did

- **BDD, then RED, then GREEN.** The scenarios are in `c0dd87a`; the RED checkpoint is
  `b8db4e7`; the fix is `6d423f1`.
  - `calculate()` and `compass_calculate` named only 8 of the 11 kinds in
    `UNKNOWN_CALCULATION`; `portfolio`, `experiment` and `update_beliefs` were missing.
    The CLI and portable script were unaffected, because argparse lists its own choices.
    `calculations.CALCULATIONS` is now the single list for both.
  - A frozen v0.6.0 schema-3 notebook with an observed and an unobserved saved plan
    (`tests/fixtures/v0.6.0-saved-experiments.sql`) must remain readable.
  - Pins for the default notebooks: CLI and portable default to `./.compass/…`, MCP to
    `~/.compass/…`. A live stdio test shows the two never meet without `COMPASS_DB`.
  - Process-level races: eight processes create one notebook, six revise one note, and
    two apply one identified event.
- **Mutation checks.**
  - Rewording `experiments._LIMITATIONS` failed only the new released-plan test; 119
    lifecycle, experiment and schema tests still passed.
  - Changing `BEGIN IMMEDIATE` to `BEGIN` failed all three process tests on each of
    three runs. Both mutations were reverted with `git checkout`.
- **Gates.**
  - The eight hash-pinned jury sources are excluded from Ruff, and a public test checks
    all nine digests (`1cea16a`, `c6afde0`).
  - Bare `pytest` now collects: it previously had 6 collection errors and now gives
    686 passed, the same as `python -m pytest`.
  - `.ontology/` is ignored.
  - GitHub CI now also runs the document policy, with full history, and
    `tests/test_mcp_live.py` (`b312c3a`).
- **Docs.**
  - The per-surface notebook defaults and the 1,000,000-character saved-plan bound
    (`91322a0`).
  - The first three crystallized learnings (`ce6e881`).
  - The owner-environment route requirement for the jury tests (`a9de305`).

## Verification before the posture commit

| Check | Result |
|---|---|
| `just check` | Pass |
| Default suite | 686 passed, 385 skipped, 17 subtests |
| Live MCP | 9 passed |
| Smoke | OK |
| Task-scope snapshots | 2 checked |
| `rocs validate` | OK |
| `just build` | Worktree clean |
| `docs-list --strict` | Pass |
| Required private jury suite, maintained owner environment | 457 passed, 0 skipped |

## What surprised me

- The whole storage suite was blind to the highest-risk change, because every test wrote
  its notebooks with the code under test.
- The workspace UBS pre-commit hook was installed on 2026-09-18, after the last code
  commit, and scans whole staged files. Its first Python commit was blocked by two
  existing SQL statements built only from constants, plus the new helper's `Popen`. Each
  now carries a reasoned `ubs:ignore`.
- The first private jury run used the wrong local environment (an upstream-release
  `dspy-lm-auth`) and gave 12 failures. All 12 were the pinned script's route guard, not
  a regression.

## Limits and deviations

- The fixture was written by the current source, whose `src/compass_c` is unchanged
  since `2c01da9`, not by an installed v0.6.0 wheel.
- The process tests ran on Linux only.
- GitHub CI still cannot run the task-scope snapshots or ROCS, since they need AK and
  the company ontology.
- The jury's optional dependencies remain undeclared; that is paused evaluation
  infrastructure.

## After publication

- **Published:** `0770f4e` went to public `main`. GitHub CI run 36263596040 passed 4/4,
  and the new document-policy and live-MCP steps ran on Python 3.11 and 3.13. AK 6007
  records the pass (evidence 10723).
- **Installs refreshed:** asked explicitly, the owner approved refreshing the installed
  skill copies. A new permission record, scoped to `0770f4e`, was written. Both physical
  installs were then replaced by managed `--replace` from the verified public head, with
  backups kept (AK 10737). Apart from the installer's receipt, all four paths are
  identical to `skills/compass`.

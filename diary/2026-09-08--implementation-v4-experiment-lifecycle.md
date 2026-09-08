---
summary: "BDD, RED/GREEN and observed use of the saved v4 experiment workflow."
read_when:
  - "Reviewing the persisted experiment lifecycle and its evidence boundaries."
type: "reference"
---

# Saved experiment lifecycle

The user asked to continue making the v4 vision real and to dogfood during the
build. The prior package version 0.5.0 is an implementation checkpoint, not the
vision's final horizon. A read-only design review identified the missing link:
experiment calculations were transient and required manual transfer into notes.

The accepted design keeps an immutable experiment plan and its single observation
in the existing notebook. It binds the model to declared evidence dependencies,
allows a fresh process to resume it, previews observations without writing, and
atomically retains the prior and posterior while invalidating dependent reasoning.
An explicit event identity makes an identical lost-response retry idempotent.
It cannot identify relabeled copies of the same underlying evidence.

Schema 3 is explicit. New notebooks use it; old schema-1/2 records retain their
existing operations and require `migrate` for the new workflow. Neither a read nor
starting a decision in an existing notebook silently migrates it. A plan supports
one observation; a subsequent experiment requires a new plan and likelihoods
appropriate to accumulated evidence.

The prospective local dogfood protocol is retained in
`evals/dogfood/v4-lifecycle/protocol.md`. The earlier 91-command exercise is a
documented friction signal, not a matched baseline for this workflow. At revision
17, build decision `3f244e36d35e410b9cd36bb353a1771c` explicitly records that limit.
Actual observed artifact-check output must supply the new experiment's result;
successful plan creation is not an observed pass.

This work does not change Softwareco's ontology ownership. `softwareco/ontology`
is the consumer workspace path. Its current submodule declaration points to
`tryingET/softwareco-ontology`, for which the connection returned 404; that does
not establish whether the backing repository is private or was never published.
No obsolete tree or fabricated scope is substituted to make governance green.

## BDD, RED and GREEN

The committed sequence preserves scenarios before failing tests and implementation:

- Schema compatibility scenarios preceded an observed 8-failure/8-pass RED run.
  Legacy behavior was pinned by frozen DDL; the new schema and migration checks
  failed as intended. The schema implementation then passed 117 focused checks.
- Saved-lifecycle scenarios preceded RED collection failure for the absent
  `compass_c.lifecycle` module. Installed-interface scenarios preceded 30 failures
  for missing CLI commands and MCP tools.
- Independent review reproduced three stale-posterior cases: changing upstream
  evidence, the observed outcome, or the posterior model left historical winners
  presented as current. BDD and RED commits preceded the repair.
- Boundary tests reproduced a 64-dependency plan that lacked room for its outcome,
  and a completed plan that still listed its consumed experiment as proposed.
  Repairs reserve an outcome dependency slot and distinguish historical proposals.
- The final focused lifecycle set passed 36 tests. An independent continuity run
  passed 221 existing v1–v3/horizon checks. The complete local suite passed
  **566 tests and 17 subtests**. An isolated installed-wheel MCP/interface run
  passed **43 tests**. The core wheel environment contained only COMPASS-C.

The runtime and skill GREEN tree was committed at local
`9771c9eda32b50cc8f01a2e64d8f256b58f03c96`. GitHub API publication recreates commit
metadata; tree-equivalent public identities are recorded separately. Retained
logs and artifact identity are in `evals/dogfood/v4-lifecycle/build-verification.json`.

The package checkpoint is 0.6.0. V1–v3 remain supported: the horizons are cumulative.
V3 reports dependency layers under shared total budgets and takes explicit
deferral values. It does not infer a timed scheduler or a real-options model.
The user specifically asked about this distinction during the build, so the
acceptance map now states it directly instead of leaving stronger capabilities
implied by broad horizon language.

## Dogfood exposed work that the software tests did not

Run 1 used two fresh participants and the frozen isolated wheel. Seven acceptance
checks passed: the handoff recovered the frozen model, the actual three-case
arithmetic check ran, preview preserved state, one apply retained the posterior
and history, and the human brief remained conditional. The effort check failed:
11 lifecycle operations exceeded the unchanged eight-operation bound.

The participants identified conflicting ordinary guidance: the general notebook
reference requested another read after a mutation, while the saved workflow
already returned validated state. The preparer also fetched a full audit view
after asking for a compact write response. The failed assessment and complete
pre-change guidance were committed before the narrow correction. The revised
reference requests a full initial response when input audit is needed, carries
the returned revision, and explains no-write proof for an isolated notebook
without redundant state reads. Unknown write outcomes and conflicts still require
reconciliation.

Run 2 freezes the same wheel, model, check, acceptance criteria and task semantics.
It changes only those two guidance references and the names of its separate
capture/notebook artifacts. Its results are retained independently; repeated
checks of the same artifact are not independent reliability evidence and their
illustrative posteriors are not combined.

The actual continuing build notebook was explicitly migrated from schema 2 to 3.
At revision 18 it records the first effort failure and the need to test the
correction, rather than declaring the vision complete from passing calculations.

The inherited handoff template still prescribed one slice per session and a branch,
contrary to the user's instruction to continue through the gates and `AGENTS.md`'s
main-first contract. Its checkpoint now reflects the cumulative v1–v4 work and
those existing instructions. This does not authorize an owner mutation, fabricate
AK state, or convert a readiness assessment into lifecycle closeout.

## Final observed workflow gate

Run 2 removed the redundant reads and completed eight successful product
operations. Its separately captured failed executable-path attempt made nine
attempts, so the effort gate remained failed. A third, prospectively frozen
capture helper resolves two exact executable aliases from the installation
manifest while retaining requested and actual arguments, working directory,
errors and all attempt counts. Eleven RED tests preceded that helper's GREEN
implementation. The original two runs and their failures remain unchanged.

Run 3 passed all eight original criteria, with eight product operations, two
discovery/resume reads, no failures or retries, and a maximum default response of
3,838 bytes. Eighteen target processes and 16 guidance/input reads were captured;
setup, help, verification and the actual experiment are reported separately from
the eight operations. The bounded check ran once in each run. These repeated
checks are not independent reliability evidence.

The complete suite, including the capture regressions, passed **577 tests and
17 subtests**. The frozen dogfood wheel remains untouched. Rebuilding after the
README gained its evidence link changed only wheel `METADATA` and its `RECORD`;
all runtime entries are byte-identical, as recorded in
`publication-wheel-comparison.json`. The original isolated-wheel MCP run passed
43 checks. GitHub commit metadata is mapped in `source-identity-map.json`, with
every paired Git tree compared before final publication.

The local ROCS build was actually attempted with the real vendored launcher and
the declared loose workspace-reference mode. It still failed because
`<repo:softwareco/ontology@main>` is unavailable. The empty task-scope check passed
with its explicit no-snapshots result. Neither result is presented as live AK
authority or as a COMPASS-C runtime dependency.

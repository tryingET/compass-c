---
summary: "Full-horizon implementation, BDD/RED/GREEN evidence and actual first-consumer use."
read_when:
  - "Reviewing the v0.5.0 implementation and its remaining proof boundaries."
type: "reference"
---

# Full vision and first-consumer dogfood

The operator corrected the earlier stopping point: source publication and CI were
one gate, not fulfillment of the entire vision. They explicitly requested all
vision gates and dogfooding during construction. The durable vision supplied four
outcome horizons; no additional numeric acceptance threshold was found. Personal
context retrieval was disabled, so no unseen historical agreement was invented.

## BDD, observed RED, then GREEN

The local history preserves specifications and observed failures before the final
implementation. GitHub API publication may recreate commit metadata and IDs; the
published parent order and source trees are verified separately.

| Checkpoint | Local commit | Observation |
|---|---|---|
| Portfolio scenarios, then tests | `b986f23`, `cd09b51` | 48 missing-module failures before implementation |
| Interface scenarios | `72f3668` | Package, portable CLI and MCP parity defined before tests |
| Evidence, experiments, scope and source provenance scenarios | `abc20d4` | Explicit observable contracts |
| Module and scope RED tests | `3286ba2` | Missing evidence/experiment modules; 49 portfolio failures including provenance; scope checker 6 failed and 2 existing fail-closed cases passed |
| Real interface RED | `046d13e`, `c38389f` | Six CLI/portable/MCP journey failures; discovery rejected missing preview/apply tools |
| Exact arithmetic RED | `27d055b` | Aggregate exact precision caused an unbounded integer-rendering failure |
| Independent review RED | `112e2f0`, `4e14b6f` | Expansive fraction syntax accepted; returned posterior failed its own reusable-model bounds |
| GREEN | `b48ab35` | Bounded standalone modules, interfaces, generated skill/plugin and truthful empty-snapshot validation |
| Installed-client discovery BDD and RED | `c8f5339`, `257b705` | Four package/portable help failures reproduced missing kind/status vocabulary |
| Discovery GREEN and generated normalization | `139578f`, `3cdc450` | Help exposes valid values and the proposed default; generated imports remain lint-clean |

Independent review found two experiment defects before publication. Exact
probability text now accepts bounded integer/fraction syntax before constructing a
Fraction, and a revised model must satisfy its own input validation. Aggregate
precision is bounded without disabling Python's integer safety limit. Review found
no additional concrete portfolio or evidence transaction defect.

## Observed software validation

- Full local Python 3.12 suite after the discovery correction: **483 passed, 17 subtests passed**.
- Isolated installed MCP wheel and interface journeys: **14 passed**.
- The separate core environment contains only `compass-c==0.5.0`; MCP is absent.
- Formatting, lint, lockfile consistency, generated drift and both skill validators passed.
- Scope checker: **8 targeted tests passed**; the actual empty-snapshot checkout
  reports `ok: no task-scope snapshots to validate`. Existing snapshots still fail
  closed without AK.

Offline uv build could not resolve an uncached Hatchling backend. The already
available Hatchling environment built the wheel and source distribution directly;
the resulting wheel was installed and tested. No dependency was added to the core.

## Actual use during construction

The main build decision is `3f244e36d35e410b9cd36bb353a1771c`. Its initial revision
11 retains the vision, alternatives, tests, limitations and reversal condition.
After observed GREEN results, a read-only evidence preview preserved the actual
snapshot, explicit apply advanced the revision once and invalidated the old
recommendation, and reconsideration produced revision 16. Sources and old content
remain visible in the exported brief and command traces.

A display-only wrapper attempted to read an incorrect summary key after the
successful writes and exports. The resulting state was read back and reconciled;
no write was replayed. This observation illustrates the documented unknown-outcome
reconciliation rule rather than claiming a rollback from a wrapper exception.

Portfolio dogfood retained 64 candidates and 24 feasible alternatives under
explicitly hypothetical planning capacities and stakeholder values. The result
scoped one review window; deferred gates remained required.

The prospective experiment dogfood declared its model before running a new
independent 32-case arithmetic check. The actual check passed; a sourced observation
updated the exact posterior to `[133/148, 15/148]`. The payoff and likelihood inputs
remain hypothetical. Accepting that conditional arithmetic for integration review
does not authorize a release or establish real-world usefulness.

## Actual guidance observations

Four fresh same-host sessions produced 32 retained answers, followed by 96
arm-masked criterion judgments under a frozen eight-case protocol. A/A scored
7/8 to 7/8; A/B scored 7/8 to 8/8 with one improvement, no regressions and an exact
sign-test p-value of 1.0. Guided answers were 14.2% longer. The single improvement
depends on a documented distinction between a generic request for valid evidence
and a specific decision-changing check. The sensitivity and all original answers
are retained; generalized benefit is not established.

The tested guidance was the exact frozen v0.4.0 skill body. v0.5.0 retains its
workflow and routing while adding links to new API references and a version bump.
A separate final-client exercise uses the actual isolated v0.5.0 wheel and final
skill bytes; its commands, provenance and brief are retained under
`evals/dogfood/2026-09-08/final-client-exercise/`. Manual loading is not native vendor
discovery, and procedural agent isolation is not a proven independent holdout.

That exercise captured 91 installed-client commands with zero failures: 9 setup/help,
3 calculations, 25 notebook mutations/previews and 54 readbacks. Preview preserved
revision 14 and database bytes; apply advanced to 15; reconsideration ended at 24.
This is substantial orchestration overhead, not a claim of effortless use. Missing
kind/status help was corrected from the observation with four RED→GREEN tests.
The exercise's original wheel hash remains unchanged in its manifest; the subsequent
help correction is verified separately on the rebuilt artifact.

The guidance study's immutable `manifest.source_commit` is local checkpoint
`cd09b516…`. Its recreated GitHub counterpart is
`309fe48ed09438900c91bfb96d53321800b2c93a`, with an identical source tree. The exact
frozen skill hash is the primary byte-level treatment identity; local commit IDs
are not presented as public GitHub links.

## Remaining external boundaries

The approved AK binary and live database are not present. Current source policy
requires its real exclusive runtime gate and database; cloning source cannot
substitute that authority. No AK task, direction, scope snapshot or lifecycle
closeout was fabricated.

Softwareco was cloned at `433e8b8e01f49b11b54d102f46055f29d41f297f`. Its actual
`.gitmodules` points to `tryingET/softwareco-ontology.git`, with ontology gitlink
`07d4b8b89f6ca436618adb42827885e9a45289c7`. The owner repository remains inaccessible.
The unchanged vendored ROCS 0.3.0 entry point runs, but strict and loose validation
both fail resolving `<repo:softwareco/ontology@main>`. Its owner contract prohibits
substituting copied sources or a metadata-free gitlink. This gate remains open.

Registry release, every vendor client, fleet adoption and automatic learning are
not required by the durable vision and were not performed. Stronger general
decision-quality claims need stronger actual evidence; software success is not a
substitute for that outcome.

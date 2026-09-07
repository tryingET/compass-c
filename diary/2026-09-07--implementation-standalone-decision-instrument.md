---
summary: "BDD-first implementation and observed evidence for the standalone v0.4.0 instrument."
read_when:
  - "Reviewing the v0.4.0 implementation, test provenance or remaining access boundaries."
type: "diary"
---

# Standalone decision instrument

The operator requested primetime readiness against `docs/project/vision.md`, using
BDD → TDD RED → GREEN, and explicitly reaffirmed that COMPASS-C is standalone.
The committed vision makes v1 a trustworthy instrument; v2-v4 remain outcome
ambitions, not blanket authorization to implement an autonomous platform.

## Observed sequence

- Baseline `56066fc`: 93 tests and 17 subtests passed.
- `512b49e`: initial BDD scenarios; `6b4eb47`: failing acceptance tests.
- Additional archive and installer BDD/RED checkpoints were committed before their fixes.
- Actual initial RED results: lifecycle 33 failed/1 passed; sensitivity 47 failed;
  CLI 10 failed; MCP 7 failed; evaluation collection failed because its module was absent.
- Further reproduced defects: precision ties, partial schema initialization races,
  malformed stored data, Unicode handling, contradictory evaluation routing,
  removed SDK API, interpreter path resolution, SDK boolean-to-revision coercion,
  workspace files in archives, shell execute modes, and skipped publication preview verification.
- Final combined local suite: 306 tests and 17 subtests passed on Python 3.12.
- The actual SDK 2.1.1 stdio suite also passed eight scenarios against an isolated
  built wheel. This is local protocol evidence, not vendor-host installation.

## Delivered behavior

Inspectable briefs retain exact claim provenance and visibly separate stale notes.
Explicit reversal conditions and sourced outcomes can be recorded. `list` supports
fresh-process recovery. `revise` atomically appends replacement history and invalidates
dependent conclusions. Schema-1 reads are unchanged; migration is explicit and transactional.
Sensitivity computes exact upper-envelope switches and preserves ties and tiny intervals.
Paired reports validate fixed observation sets and expose regressions without claiming causality.

Generated portable scripts and plugin copies come from the canonical runtime. The
core still has zero runtime dependencies. MCP is optional; AK is development coordination.
Archives use declared source paths and exclude local state and unrelated workspace material.

## Review and evidence limits

Independent review found two additional malformed-history/routing inconsistencies;
both received regression tests and fixes. No P0/P1 finding was reported. Reproduced
software behavior is the basis for local readiness; favorable synthetic scores are not
host usefulness evidence. There was no controlled A/A or A/B host run, account-level
installation, learning promotion, or release tagging.

The GitHub connection rejected object creation with HTTP 403 `Resource not accessible
by integration`; shell Git has no write credentials. No remote ref was changed.
The complete implementation remains in local Git, ready for publication with write access.

AK source was inspected through the authenticated GitHub connection. Its declared
approved binary and canonical live database are absent here. No replacement database,
task state, scope snapshot, or work-items projection was invented. Reconcile actual
AK task/direction state through the owner's approved runtime when it is available.

## Final repository gates

`TMPDIR=<scratch-temp> ./scripts/ci/full.sh` passed its complete fast phase:
formatting, lint, generated drift, both skill validators, 306 tests/17 subtests,
and the committed document-freshness policy. The full command remained blocked
by the missing approved AK command and the ROCS launcher's `/proc/self/exe`
environment requirement. Running the unchanged vendored ROCS entry point directly
resolved the launcher problem but exposed external ontology prerequisites.

The public core ontology was cloned at exact v0.2.0, commit
`76f31bc5d42a77bc2c0fd24c8b30708f907fbd44`. Company ontology
`tryingET/softwareco-ontology` returned 404 through the connected account and
could not be cloned. Direct ROCS build and validation therefore remained blocked
on `<repo:softwareco/ontology@main>`. No ownership, policy, or validation gate was
weakened to obtain a passing result.

Wheel and source distribution were built offline from a clean declared-source
snapshot using the installed Hatchling backend. The three deterministic archives
were generated and checked. The final worktree is committed; remote publication,
organization-governance checks, and actual host usefulness evidence remain distinct
unfinished external steps.

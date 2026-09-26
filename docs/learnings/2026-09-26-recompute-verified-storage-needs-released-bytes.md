---
summary: "Storage verified by recomputation needs a frozen fixture written by a released version; tests that build their notebooks with current code cannot see output drift."
read_when:
  - "You change experiment calculation output, or any stored value that is verified by recomputing it."
  - "You add a self-verifying storage format."
type: "learning"
---

# Recompute-verified storage needs released bytes in the tests

## Context

COMPASS-C stores each saved experiment plan's parameters and computed proposal, and on
every read recomputes the proposal and requires exact equality. The 2026-09-26 risk
probe showed that rewording `experiments._LIMITATIONS` alone made every saved plan, and
`brief`, fail with `INVALID_STORAGE`.

## Discovery

Every existing lifecycle, experiment and schema test created its notebooks with the
code under test. Stored and recomputed output therefore always agreed, and the suite
could not see drift. With the wording mutation applied, 119 of those tests still
passed. Only a notebook written by a released version and frozen as bytes fails.

## Evidence

- [`tests/fixtures/v0.6.0-saved-experiments.sql`](../../tests/fixtures/v0.6.0-saved-experiments.sql):
  schema-3 notebook written by the v0.6.0 runtime, with observed and unobserved plans.
- `tests/test_schema3.py::test_saved_plans_written_by_v060_remain_readable`: fails under
  the wording mutation; it is the only failure among 120 tests.
- `evals/rethink-2026-09-26/risk-probes/probe_brittle.py.txt`: the original probe.

## Application

For any stored value that is re-derived and compared, keep one frozen fixture per
released writer version and never regenerate it to make a test pass. Changing the
output then needs a versioned comparison or an explicit migration, which the ADR
already requires. The same applies to caches keyed by derived hashes and to generated
artifacts checked for drift against released copies.

## TIP Candidate

Yes. It generalizes to any template-generated repository that stores derived data. It
is cheap: one fixture and one test per released storage writer.

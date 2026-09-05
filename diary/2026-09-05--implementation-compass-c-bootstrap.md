---
summary: "Initial COMPASS-C repository bootstrap and implementation evidence."
read_when:
  - "You need the raw implementation-session context behind the first release."
type: "diary"
---

# COMPASS-C bootstrap

## Intent

Create `tryingET/compass-c` from Softwareco `tpl-project-repo` with the Python software pack,
using the operator's public shared conversation as the product and implementation brief.

## Implemented

- canonical Python library and JSON CLI;
- seven bounded calculations;
- six revisable-notebook operations;
- side-effect-free construction, calculation, and reads;
- portable skill with conditional references and 24 development cases;
- generated standalone skill scripts and skills-only plugin;
- deterministic archives, local installer, remote publication readback, and backup/rollback path;
- optional provisional MCP adapter;
- project docs, standard Justfile surface, and pinned-action CI.

## Evidence observed before initial commit

- `just check`: passed;
- `just test`: 62 tests and 17 subtests passed on Python 3.13.12;
- `just build`: wheel, source distribution, and three COMPASS archives built;
- skill structural validator: passed;
- generated skill and plugin drift checks: passed.

`just ci` initially reached and passed product tests, then correctly blocked on the template's
living-product-posture two-commit policy. The intended resolution is an evidence baseline commit
followed by exactly one posture-validation commit.

## Boundaries

The shared conversation's earlier test reports informed scope but were not counted as local proof.
No host behavioral A/B evaluation, live MCP round-trip, or ChatGPT account installation occurred.
The exact requested license was preserved and must not be called ordinary MIT.

---
name: compass-c-maintainer
description: >-
  Maintain the COMPASS-C Python package, generated portable skill, local notebook,
  installer, archives and repository validation. Use for COMPASS-C code defects,
  regression tests, packaging changes or integrating an approved skill revision.
  Do not use for a decision brief (use compass), authoring or optimizing an Agent
  Skill as the primary deliverable (use agent-skill-engineer), paragraph reading,
  another repository, or fleet/template rollout.
compatibility: COMPASS-C checkout; Python 3.11+, uv and just. Project discovery depends on host trust and loading settings.
version: "0.1.0"
owner: "COMPASS-C maintainers"
last_verified: "2026-09-05"
baseline_version: "891e8e7da37c3675ae4fa0d67b822a61660ee604"
source_policy: versioned
eval_suite: evals/cases.json
routing:
  triggers:
    - repair COMPASS-C runtime, notebook, installer or packaging defects
    - integrate an approved COMPASS skill revision and run repository checks
  primary_action: maintain
metadata:
  evidence_status: "provisional-behavior; structural-and-regression-checks-only"
---

# Maintain COMPASS-C

Fix the owning executable boundary and verify its actual outputs. Do not convert a
successful calculation, complete notebook or structural skill audit into decision
quality, action permission, installation, or behavioral-improvement evidence.

## Boundary and inspection

1. Resolve the repository containing this skill (three parents above this directory).
   Confirm its identity and dirty state before using repo-relative commands. Do not
   assume a shell directory change loads the target's instructions.
2. Read repo `AGENTS.md`, `docs/engineering.local.md` and the compact engineering
   policy projection, then the exact task scope and affected code/tests. Current
   AK access policy takes precedence over stale executable recipes in templates;
   use the approved gate with its explicit database routing, never direct SQLite.
3. Keep one primary owner. The `compass` skill supplies a conditional comparison
   when requested; it does not replace this maintenance workflow. For skill-only
   changes hand off to `agent-skill-engineer`, then return for integration/tests.
4. If the relevant skill is unavailable, report that limitation and locate its
   source through the host's owner routing. Do not install or copy a global skill
   silently. Read [Improvement intake](references/improvement.md) before using KES
   or session-derived lessons to propose a change.

## Workflow: change the causal layer

`{repo}` denotes the confirmed checkout root, not a bundled skill resource.

| Observation | Owning response |
|---|---|
| Wrong calculation or notebook behavior | Repair `src/compass_c/` and test runtime outputs |
| Generated script drift | Run `python scripts/build_skill.py`; never hand-edit generated scripts |
| Wrong skill selection or instructions | Skill-engineering handoff with fixed routing/behavior cases |
| Malformed evaluation accepted or validator crashes | Repair `{repo}/scripts/validate_skill.py` and adversarial tests |
| Installation or publication claim | Inspect `docs/project/installation.md` and exact observed host state |
| Wrong source interpretation or puzzle assignment | Return to the reading/source owner, not COMPASS-C |
| Missing AK, KES, FCOS or template behavior | Owner handoff; do not simulate it in local records |

For a defect, demonstrate the failure on synthetic inputs before fixing it. Preserve
baseline successes too. Inspect affected schema/storage compatibility and generated
artifacts; a local fix must not silently invalidate stored decisions or distributions.

## Verification and reporting

From the confirmed repo root:

- run focused regression tests first;
- run `just check` for formatting, lint, generated drift and both skill packages;
- run `just test` and the repo-declared `just ci` contract before merge;
- use `just build` when distribution contents change; archive construction is not
  publication and must not trigger installation;
- inspect the exact diff, output identities and remaining proof gaps.

Honor owner gates before any database-bearing validation. A blocked check remains
blocked, not passed. Do not run providers or live clients merely to turn a provisional
claim green. Unknown write outcomes require reconciliation before retry.

Report the reproduced cause, changed files, tests and failure preservation. Record
accepted evidence through the owning task; distinguish a candidate skill in Git from
host-loaded guidance, observed use and measured behavioral improvement. Promotion,
installation, release and fleet rollout each require their own owner acceptance.

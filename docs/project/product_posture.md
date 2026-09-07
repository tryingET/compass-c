---
summary: "Current versus target product maturity for COMPASS-C."
as_of: "2026-09-07"
last_validated: "2026-09-07"
last_validated_commit: "1bb2382dd324fa3b3bc315605313bc642f5cbe8c"
evidence_paths:
  - "README.md"
  - "src/compass_c"
  - "tests"
  - "skills/compass"
  - "scripts/build_skill.py"
  - "scripts/build_archives.py"
  - "scripts/validate_skill.py"
  - "scripts/configure_mcp.py"
  - "install_skill.py"
  - "integrations"
  - "pyproject.toml"
  - "uv.lock"
  - ".github/workflows/ci.yml"
  - ".pi/skills/compass-c-maintainer"
  - "docs/project/verified-publication.json"
  - "diary/2026-09-07--publication-v0.4.0-readback.md"
  - "release.json"
read_when:
  - "When assessing maturity, rollout, or proof gaps"
type: "reference"
---

# Product posture

## Posture in one sentence

COMPASS-C v0.4.0 has a verified standalone software path for inspectable, revisable
local decisions; measured host usefulness and vendor-client adoption remain unproved.

## Product maturity map

| Area | Current posture | Target posture | Remaining proof boundary |
|---|---|---|---|
| Standalone runtime | Standard-library core, dependency-free wheel execution, CLI and portable-script journey tests. | Dependable local decision instrument. | Wider operating-system and long-lived deployment evidence. |
| Briefs and sensitivity | Provenance-preserving briefs, explicit reversal-condition notes, exact probability-path preference intervals and ties. | Inspectable decisions and decision-changing uncertainty. | Recorded claims, model adequacy and conditions still require judgment. |
| Living records | Listing, atomic replacement history, dependency invalidation and sourced outcomes; explicit transactional schema-1 to schema-2 migration with frozen compatibility fixtures. | Reconsider decisions without rewriting history. | No background monitoring, automatic source verification or protected audit log. |
| Skill behavior | Existing 24-case portable and 8-case maintainer development corpora; fail-closed paired A/A and A/B reporting, regressions and statistical uncertainty. | Reliable selection and improved decisions in target hosts. | No controlled host observations collected; author-visible fixtures are not independent behavioral evidence. |
| Installation and archives | Declared-source deterministic archives, no-overwrite installation, verified publication preview and bounded replacement. | Reproducible client-specific adoption and rollback. | Account installation, license clearance and fresh-host readback remain external. |
| MCP | SDK 2.1.1 pinned; native installed adapter; ten tools; genuine local stdio sessions verified against an isolated wheel. | Directly verified supported client paths. | Vendor-host discovery and shared-service requirements are not covered by local SDK tests. |
| Repo skill adoption | Repo-owned maintainer guidance remains separate from standalone skill/plugin archives. | Recipient-owned improvement based on verified learning. | KES acceptance, controlled behavioral improvement and cross-repo adoption remain with their owners. |

## Observed validation

For the implementation recorded in the evidence baseline above, the local Python 3.12 suite passed **306 tests
and 17 subtests**. It includes seven BDD feature files and executable acceptance
coverage for fresh-process package/portable journeys, compatibility, malformed input,
concurrency, exact arithmetic, paired reports, installation and archive boundaries.
The actual SDK suite passed eight scenarios against an isolated built wheel.
The core wheel also executed with no dependencies installed and no MCP present.
Formatting, lint and generated skill/plugin checks passed.

GitHub Actions [run 34170286584](https://github.com/tryingET/compass-c/actions/runs/34170286584)
completed successfully for published source commit
`d839c97b9bc169672c2f25935e770017a0bb5990`. All four jobs passed: core verification
and isolated MCP wheel sessions on Python 3.11 and 3.13. The dated publication
receipt records that observed run; it does not establish organization-governance
approval or measured host usefulness.

BDD scenarios and actual RED checkpoints preceded GREEN implementation. The session
diary records the sequence and independent review findings. The repository retains
its provisional evidence label: software tests alone cannot complete the v1 vision's
measured-usefulness criterion, and v2-v4 remain ambitions rather than release promises.

## Status-language and ownership rules

- Local tests prove only the paths they execute.
- A paired report authenticates neither the scores nor the claimed host execution.
- A complete brief is not a verified or authorized decision.
- A generated archive is not an installation; a local SDK session is not a vendor-host connection.
- Publishing a repository does not grant account, release or fleet-rollout authority.
- AK and other foundry systems are development coordination tools, not COMPASS-C runtime dependencies.

Live AK tasks, direction, evidence and decisions retain their existing owner. The
approved AK runtime and live database were unavailable in this environment; no task
projection or scope snapshot was fabricated. This document is a maturity projection,
not an execution queue. Source publication of v0.4.0 on `main` is verified by GitHub
API and git transport readback, as recorded in the
[dated receipt](verified-publication.json) and
[publication diary](../../diary/2026-09-07--publication-v0.4.0-readback.md).
No release tag, package-registry release, account installation or controlled host
evaluation is claimed.

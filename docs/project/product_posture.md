---
summary: "Current versus target product maturity for COMPASS-C."
as_of: "2026-09-08"
last_validated: "2026-09-08"
last_validated_commit: "c89e6d22e2c8712173071ceca0b67ff459af486e"
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
  - "evals"
  - "docs/project/vision-validation.md"
  - "docs/project/usage.md"
  - "diary/2026-09-08--implementation-full-vision-dogfood.md"
  - "scripts/check-task-scope-snapshots.sh"
  - "scripts/lib/check-task-scope-snapshots.py"
read_when:
  - "When assessing maturity, rollout, or proof gaps"
type: "reference"
---

# Product posture

## Posture in one sentence

COMPASS-C v0.5.0 implements bounded standalone workflows across all four vision
horizons and has actual first-consumer observations; generalized decision-quality
improvement and the inaccessible company ontology gate remain unresolved.

## Product maturity map

| Area | Current posture | Target posture | Remaining proof boundary |
|---|---|---|---|
| Standalone runtime | Standard-library core, dependency-free wheel execution, CLI and portable-script journey tests. | Dependable local decision instrument. | Wider operating-system and long-lived deployment evidence. |
| Briefs and sensitivity | Provenance-preserving briefs, explicit reversal-condition notes, exact probability-path preference intervals and ties. | Inspectable decisions and decision-changing uncertainty. | Recorded claims, model adequacy and conditions still require judgment. |
| Living records | Listing, atomic sourced evidence batches with read-only preview, dependency invalidation, revision history and outcome review; explicit compatible migration. | Reconsider decisions without rewriting history. | No background monitoring, automatic source verification or protected audit log. |
| Coordinated decisions | Bounded feasible portfolios, exact shared capacity, dependency layers, exclusions, explicit deferral values and preserved stakeholder optima/disagreement. | Coordinate choices while retaining each owner's authority. | Additive caller-supplied values are assumptions; dependency layers do not schedule work or reserve resources. |
| Experimental decisions | Finite one-observation proposals with no-test baseline, EVSI/net cost and outcome branches; explicit observed-result Bayesian updates retain the prior and reusable exact posterior. | Identify decision-changing uncertainty and learn from informative observations. | Supplied likelihoods are not validated; no experiment is executed and omitted model structure remains the owner's responsibility. |
| Skill behavior | Existing development corpora plus actual frozen same-host A/A and A/B observations: 32 answers, retained grading and paired reports. | Reliable selection and improved decisions in target hosts. | One grading-sensitive improvement, no observed regressions, p=1.0; generalized benefit and native discovery unestablished. |
| Installation and archives | Declared-source deterministic archives, no-overwrite installation, verified publication preview and bounded replacement. | Reproducible client-specific adoption and rollback. | Account installation, license clearance and fresh-host readback remain external. |
| MCP | SDK 2.1.1 pinned; native installed adapter; twelve tools; genuine local stdio sessions verified against an isolated wheel. | Directly verified supported client paths. | Vendor-host discovery and shared-service requirements are not covered by local SDK tests. |
| First consumer | Actual build notebook, prospective arithmetic experiment and fresh installed-client exercise; observed CLI-help friction repaired through RED/GREEN. | Useful self-correction during this repository's own work. | 91-command client exercise includes substantial readback overhead; it is not a claim of effortless use. |
| Repo skill adoption | Repo-owned maintainer guidance remains separate from standalone skill/plugin archives. | Recipient-owned improvement based on verified learning. | KES acceptance, controlled behavioral improvement and cross-repo adoption remain with their owners. |

## Observed validation

At the evidence baseline above, the local Python 3.12 suite passed **483 tests
and 17 subtests**. Acceptance covers fresh processes, compatibility, malformed input,
concurrency, exact arithmetic, portfolios, experiments, evidence transactions,
paired reports, installation and archive boundaries. Fourteen SDK/interface scenarios
passed against an isolated v0.5.0 wheel. The separate core environment contained
only COMPASS-C, with no MCP or runtime dependencies. The subsequent help correction
passed four discovery regressions and was checked on the rebuilt installed core.
Formatting, lint, lockfile consistency and generated skill/plugin checks passed.

The [vision acceptance map](vision-validation.md) connects every horizon to its
observable evidence. The retained host diagnostic tests manually supplied frozen
v0.4.0 guidance; a separate client exercise records the v0.5.0 wheel and final skill
hashes. Earlier source-publication receipts remain dated observations, not claims
that every later commit was checked or every host installed the skill.

BDD scenarios and actual RED checkpoints preceded GREEN implementation. The session
diary records the sequence and independent review findings. The repository retains
its provisional evidence label: actual local usefulness is now observed, while
software tests and a small diagnostic cannot establish generalized benefit or
guarantee the outcome ambitions for every future decision.

## Status-language and ownership rules

- Local tests prove only the paths they execute.
- A paired report authenticates neither the scores nor the claimed host execution.
- A complete brief is not a verified or authorized decision.
- A generated archive is not an installation; a local SDK session is not a vendor-host connection.
- Publishing a repository does not grant account, release or fleet-rollout authority.
- AK and other foundry systems are development coordination tools, not COMPASS-C runtime dependencies.

Live AK tasks, direction, evidence and decisions retain their existing owner. The
approved AK runtime and live database were unavailable; no authority or projection
was fabricated. The empty-snapshot check now reports its true no-op without requiring
AK, while actual snapshots remain fail-closed. The canonical company ontology at
`tryingET/softwareco-ontology` is inaccessible, so repository-wide ontology validation
remains blocked. This document is a maturity projection, not an execution queue.
No release tag, registry release, vendor-account installation, KES promotion or wider
rollout is claimed. None becomes a COMPASS-C core runtime dependency.

---
summary: "Current versus target product maturity for COMPASS-C."
as_of: "2026-09-11"
last_validated: "2026-09-11"
last_validated_commit: "2c01da9845e181ef247925b1a57f068ffe9d6832"
evidence_paths:
  - "README.md"
  - "src/compass_c"
  - "tests"
  - "skills/compass"
  - "scripts/build_skill.py"
  - "scripts/build_archives.py"
  - "scripts/validate_skill.py"
  - "scripts/configure_mcp.py"
  - "scripts/mcp_call.py"
  - "scripts/report_glm_dogfood.py"
  - "scripts/ci/fast.sh"
  - "Justfile"
  - "docs/project/evaluation.md"
  - "docs/project/installation.md"
  - "diary/2026-09-11--verification-glm-native-and-recovery-boundaries.md"
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
  - "diary/2026-09-08--implementation-v4-experiment-lifecycle.md"
  - "next_session_prompt.md"
  - "scripts/check-task-scope-snapshots.sh"
  - "scripts/lib/check-task-scope-snapshots.py"
read_when:
  - "When assessing maturity, rollout, or proof gaps"
type: "reference"
---

# Product posture

## Posture in one sentence

COMPASS-C v0.6.0 preserves the cumulative workflow and has observed Pi/GLM skill
acquisition and live MCP use; reliable decision-quality improvement, unattended
write/retry safety and actual personal OpenAI account installation remain unproved.

## Product maturity map

| Area | Current posture | Target posture | Remaining proof boundary |
|---|---|---|---|
| Standalone runtime | Standard-library core, dependency-free wheel execution, CLI and portable-script journey tests. | Dependable local decision instrument. | Wider operating-system and long-lived deployment evidence. |
| Briefs and sensitivity | Provenance-preserving briefs, explicit reversal-condition notes, exact probability-path preference intervals and ties. | Inspectable decisions and decision-changing uncertainty. | Recorded claims, model adequacy and conditions still require judgment. |
| Living records | Atomic sourced evidence batches, read-only previews, dependency invalidation, history and outcome review. Frozen schema-1/2 operations remain supported; experiment storage requires explicit schema-3 migration. | Reconsider decisions without rewriting history. | No background monitoring, automatic source verification or protected audit log. |
| Coordinated decisions | Bounded feasible portfolios, exact shared capacity, dependency layers, exclusions, explicit deferral values and preserved stakeholder optima/disagreement. | Coordinate choices while retaining each owner's authority. | Additive caller-supplied values are assumptions; dependency layers do not schedule work or reserve resources. |
| Experimental decisions | Frozen bounded plans, cold resume, identified observation preview/apply, exact prior/posterior history and atomic note invalidation across CLI, portable skill and MCP. Duplicate event retries do not incorporate evidence again; changed evidence makes the retained model historical. | Identify decision-changing uncertainty and learn from informative observations. | One observation per plan; subsequent likelihoods and model adequacy remain caller-owned. Sources are unverified; the product does not execute experiments or detect relabeled duplicate evidence. |
| Skill behavior | Prior diagnostic plus 96 fresh Pi/GLM-5.3-flash trials: native acquisition observed, 48 A/A then 48 A/B captures, all failures retained. | Reliable selection and improved decisions in target hosts. | A/B answer-rubric passes 19/24 versus 20/24, two improvements and one regression, p=1.0. Same-model grading and author-visible cases do not establish general benefit. |
| Installation and archives | Declared-source archives, public-head-verified v0.6.0 skill install, disposable managed upgrade with runnable backup, Pi/Codex discovery and withdrawal observed. | Reproducible client-specific adoption and rollback. | Personal OpenAI account/client selection, installation and fresh-account readback remain external. The operator's limited permission is not a general license change. |
| MCP | SDK 2.1.1 pinned; seventeen tools; local wheel sessions and an actual GLM-driven Pi SDK workflow using six core operations observed. Missing-store errors now state their limited scope. | Directly verified supported client paths. | Custom Pi integration is not default host/account installation. One of three targeted recovery probes still offered unsafe retry assurance; no unattended-write approval or shared-service readiness. |
| First consumer | Three prospective saved-workflow runs with fresh preparer/resumer pairs. Two failed effort gates exposed guidance and capture friction; the third passed all eight unchanged criteria with eight product attempts and no failures. | Useful self-correction during this repository's own work. | Small author-visible local exercise; full audit output is lengthy and generic briefs can still flag missing narrative categories. Capture ergonomics do not establish product benefit. |
| Repo skill adoption | Repo-owned maintainer guidance remains separate from standalone skill/plugin archives. | Recipient-owned improvement based on verified learning. | KES acceptance, controlled behavioral improvement and cross-repo adoption remain with their owners. |

## Observed validation

At the current evidence baseline, the local Python 3.13.12 suite with explicit
host opt-ins passed **605 tests and 17 subtests**. Ordinary CI skips the three
installed-host probes, which are run separately. Acceptance includes compatibility,
concurrency, exact arithmetic, portfolios, experiments, evidence transactions,
paired reports, installation, archives and raw-to-grade transformation integrity.
Formatting, lint and generated skill/plugin checks passed. Forty-three SDK/interface
scenarios also passed against an isolated v0.6.0 wheel. Final committed-state CI and
build readbacks belong to AK 5641; these earlier passes do not substitute for that gate.

The [current GLM study](../../evals/observations/2026-09-11-glm-native/README.md)
retains the actual protocol, reports, failures, normalization records and recovery
assessment. All 96 raw-to-grade transformations were checked without changing the
paired values or resampling judgments. The larger combined case/routing gains must
not be read as reasoning gains against a baseline with no skill available.

Earlier Python 3.12/577-test and publication-wheel receipts remain historical evidence
of their original revisions. The pure-core and publication-wheel comparison in
`evals/dogfood/v4-lifecycle/publication-wheel-comparison.json` is not a publication
receipt for this later local change.

The [vision acceptance map](vision-validation.md) connects every horizon to its
observable evidence. The retained host diagnostic tests manually supplied frozen
v0.4.0 guidance. The separate saved-workflow runs freeze the v0.6.0 wheel, complete
guidance bytes, tasks, models and actual check before participant execution.
Run 3 retained 18 successful target processes, 16 input/guidance reads and a
3,838-byte largest default response; the eight product operations are one category
within those measured costs. Earlier failed results remain failed. Source commit
metadata is paired with identical Git trees in the retained identity map.
Earlier source-publication receipts remain dated observations, not claims
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

Live AK tasks, direction, evidence and decisions retain their existing owner.
The earlier publication environment lacked AK and could not retrieve the company
ontology source; those are historical observations, not current local gate claims.
Current work uses AK 5641 and this checkout's declared validation contract. The
empty-snapshot check remains a truthful no-op, while actual snapshots fail closed.

The one-off model drivers were withdrawn from the reusable command surface after
review found cross-process budget-custody gaps. Exact archival source remains for
inspection. Actual controller-serialized usage stayed below the allowance; global
budget enforcement was not proved and future live reuse needs execution-owner gates.

This document is a maturity projection, not an execution queue. No release tag,
registry release, new public push, vendor-account installation, KES promotion or
wider rollout is claimed. None becomes a COMPASS-C core runtime dependency.

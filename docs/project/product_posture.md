---
summary: "Current versus target product maturity for COMPASS-C."
as_of: "2026-09-05"
last_validated: "2026-09-05"
last_validated_commit: "9726d109212d54cea252d5f340cf6494720ff7c2"
evidence_paths:
  - "README.md"
  - "src/compass_c"
  - "tests"
  - "skills/compass"
  - "scripts/build_skill.py"
  - "scripts/validate_skill.py"
  - ".pi/skills/compass-c-maintainer"
read_when:
  - "When assessing maturity, rollout, or proof gaps"
type: "reference"
---

# Product posture

## Posture in one sentence

COMPASS-C has a locally testable library, CLI, skill, and packaging path; it is converging on a
cross-client decision aid, with behavioral and live-integration evidence still missing.

## Product maturity map

| Area | Current posture | Target posture | Main gap | Proof of closure |
|---|---|---|---|---|
| Core capability | Seven calculators and six record operations are locally testable. | Stable, versioned decision support with migrations. | No long-lived compatibility history. | Upgrade tests across released notebook schemas. |
| Skill behavior | Narrow routing contract and 24 development cases exist. | Reliable selection and improved decisions across target clients. | No controlled A/A and paired A/B runs. | Frozen-corpus results with variance and regressions. |
| Repo skill adoption | Repo-local `compass-c-maintainer` candidate defines maintenance, skill-engineering handoffs and KES-qualified improvement intake; eight author-visible routing/pressure cases accompany it. | Recipient-owned skills improve repeated work from verified learning. | Fresh-host discovery/use, controlled behavior evidence and cross-repo adoption are unproved. | Host readback, fixed paired evaluations, recipient acceptance and withdrawal proof. |
| Installation | Deterministic archives and local installer are implemented. | Reproducible client-specific install and rollback. | Account-level ChatGPT installation is external and license-gated. | Direct host readback and fresh-session canaries. |
| MCP | Local adapter source exists. | Supported local/shared integration profile. | No live SDK/client round-trip. | Version-pinned integration test against a target client. |

## Status-language rules

- Local tests prove only the behavior they directly execute.
- Development cases are not successful model evaluations.
- Generated archives are not installations.
- An adapter file is not a connected MCP service.
- A complete notebook is not a verified or authorized decision.

Live execution truth belongs in AK tasks/evidence when active work is registered. This document is
a maturity projection, not a roadmap or queue.

## Selected product emphasis

The operator-selected first step is standalone COMPASS-C plus repo-skill quality and
KES-qualified improvement, not waiting for the statechart foundry. The full v1-v4
ambition remains in `vision.md`; task 5424 owns the first-consumer implementation.
The repo-local skill stays out of the standalone skill and skills-only plugin
archives; it remains in the source toolkit. It does not install
`agent-skill-engineer` globally or implement a KES runtime.

The structural validator covers both skill packages and rejects malformed corpus,
case and criterion shapes with contract errors. This is integrity protection, not
proof of selection accuracy, improved decisions, or automatic learning. At the
implementation baseline above, local checks pass with 93 tests and 17 subtests;
the methodology's strict skill audit reports zero errors and warnings. Independent
review accepted the bounded candidate with minor revisions, now addressed. Full
posture-bound CI and completion receipts belong to task 5424; prior publication
receipts remain evidence of their original release, not publication of this change.

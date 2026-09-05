---
summary: "Current versus target product maturity for COMPASS-C."
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

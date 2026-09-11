---
summary: "Current versus target product maturity for COMPASS-C."
as_of: "2026-09-11"
last_validated: "2026-09-11"
last_validated_commit: "6116ac46bed5a87b97c5ba9c01d8eb97e28d5c5d"
evidence_paths:
  - "README.md"
  - "src/compass_c"
  - "tests"
  - "skills/compass"
  - "scripts/build_skill.py"
  - "scripts/validate_skill.py"
  - "scripts/configure_mcp.py"
  - "scripts/build_archives.py"
  - "scripts/dogfood_pi.mjs"
  - "scripts/ci/fast.sh"
  - "integrations/mcp_server.py"
  - "docs/project/installation.md"
  - "pyproject.toml"
  - "uv.lock"
  - "Justfile"
  - ".pi/skills/compass-c-maintainer"
read_when:
  - "When assessing maturity, rollout, or proof gaps"
type: "reference"
---

# Product posture

## Posture in one sentence

COMPASS-C has locally dogfooded installation, Pi/Codex discovery, and live Python MCP SDK
transport. Behavioral efficacy, model-driven host integration, and account installation remain
unproved; local discovery is not automatic skill selection.

## Product maturity map

| Area | Current posture | Target posture | Main gap | Proof of closure |
|---|---|---|---|---|
| Core capability | Seven calculators and six record operations are locally testable. | Stable, versioned decision support with migrations. | No long-lived compatibility history. | Upgrade tests across released notebook schemas. |
| Skill behavior | Narrow routing contract and 24 development cases exist. | Reliable selection and improved decisions across target clients. | No controlled A/A and paired A/B runs. | Frozen-corpus results with variance and regressions. |
| Repo skill adoption | Repo-local `compass-c-maintainer` candidate defines maintenance, skill-engineering handoffs and KES-qualified improvement intake; eight author-visible routing/pressure cases accompany it. | Recipient-owned skills improve repeated work from verified learning. | Fresh-host discovery/use, controlled behavior evidence and cross-repo adoption are unproved. | Host readback, fixed paired evaluations, recipient acceptance and withdrawal proof. |
| Installation | Isolated installer CLI, exact hashes, helper execution, Pi/Codex fresh-process discovery and withdrawal pass; runtime caches/SQLite sidecars excluded from rebuilt archives. | Reproducible client-specific install and rollback. | Model-driven canaries, managed replacement and account-level ChatGPT installation not exercised here. | Permission-cleared target-host readback, behavioral canaries and replacement/rollback proof. |
| MCP | MCP 2.1.1 local stdio SDK round-trip passes all six tools, restart persistence, strict revision rejection and no-storage read/calculation checks. | Supported local/shared integration profile. | Agent-host MCP configuration, other versions and shared-service controls unverified. | Direct target-host round-trip and version-specific security/integration tests. |

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
proof of selection accuracy, improved decisions, or automatic learning. Task 5424
retains the historical skill-audit and independent-review receipts for that revision;
they are not a fresh audit of later changes.

At this implementation baseline, the combined local suite with MCP and host opt-ins
passes **123 tests and 17 subtests**, without skips. The three host probes use Pi
0.84.4 and Codex CLI 0.128.0 in disposable homes with networking disabled; they are
skipped by ordinary CI. The eight live MCP cases are explicitly required by CI.
See `installation.md` for exact commands, versions, assertions, and limits.

AK task 5641 owns the local dogfood evidence and unfinished request. The operator
expressly declined restricted-provider permission and supplied no model evaluation
budget. No model trial or ChatGPT upload was attempted. Behavioral A/A and paired
A/B evaluation require an approved model/budget; account installation additionally
needs applicable permission and target account/UI access. Neither gate was replaced
by a simulated success. This revision was not publicly pushed or permanently installed;
prior publication receipts remain evidence of their original release only.

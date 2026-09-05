---
summary: "Agent operating contract for generated project repositories."
read_when:
  - "Read when changing the generated tpl-project-repo AGENTS.md operating contract."
type: "reference"
---

# AGENTS.md — compass-c

## Intent
Template for a delivery project repo (project context + code + tests).

## Guardrails
- No secrets in git.
- Main-first workflow: commit directly to `main` for normal work; use a review branch/PR only when the operator requests a gate.
- Treat `docs/_core/**` as immutable.
- Track deferred work in Agent Kernel; keep `governance/work-items.json` as the exported projection via plain installed `ak` (avoid ad-hoc TODO comments and manual JSON authority confusion).
- When explicit task scope is in play, author it in AK and freeze repo-consumption snapshots via `ak task scope show|export ...`; treat `governance/task-scopes/AK-*.snapshot.json` as AK exports, not hand-authored truth.

## AK-native route guardrails
- If this repo declares AK-native task, direction, or route authority, read the relevant AK task and route/open-frame status before inventing new work.
- Generic operator input such as `proceed` continues the active execution task when one exists; it does not authorize lifecycle closeout, source-owner mutation, publication, or knowledge promotion.
- Treat closeout/readiness rows as gate inputs, not lifecycle authorization.
- Treat docs, work-items JSON, task-scope snapshots, and direction explorer exports as projections unless the repo declares otherwise; AK DB remains runtime authority for AK tasks, direction, evidence, and decisions.
- Handoff instead of editing by convenience when facts belong to Prompt Vault, ROCS, Pi/runtime, KES, steward/publication, template propagation, Oracle/DSPx, or another repo.
- Treat `docs/project/vision.md` as the durable product direction path when present.
- Treat `docs/project/product_posture.md` as a product-maturity bridge, not a queue, roadmap, changelog, or execution authority.
- Do not revive SG/TG/OP markdown planning where AK-native direction authority is declared; legacy `strategic_goals.md`, `tactical_goals.md`, `operating_plan.md`, or `operational_plan.md` files are archive/projection only unless a repo-local owner decision explicitly says otherwise.

## Deterministic tooling policy (ROCS-first)
- Prefer `ak work-items <import|export|check> ...` for repo-local work-items projection operations.
- Prefer `./scripts/rocs.sh <args...>` before ad-hoc inline scripting.
- Use `./scripts/preflight-repo-census.sh [scope]` for shallow multi-repo status checks.
- For ontology/policy checks, use ROCS commands as the default execution path.
- Use inline Python only as an explicit escape hatch when no deterministic command exists.

## COMPASS-C product contract
- `src/compass_c/` is the canonical runtime; never hand-edit `skills/compass/scripts/`.
- Run `python scripts/build_skill.py` after runtime changes and check generated drift in CI.
- Preserve the advisory boundary: no record, review, calculation, skill, or adapter grants action permission.
- Keep development evaluation cases labeled as author-visible; do not claim behavioral improvement without controlled host evidence.
- Build archives and plugin files from the canonical skill; archive generation is not installation.
- Review the provider rider in `LICENSE` before host installation or distribution.

## Stack contract
- If this repo ships a language-specific software pack, keep the engineering contract explicit:
  - `policy/engineering-lane.json` declares the upstream `engineering-core` lane reference and the executable retrieval command
  - `docs/engineering.local.md` records repo-local overrides on top of that lane contract
  - consult `policy/engineering-lane.json` before invoking `engineering-core` directly; do not assume repo-local `lanes/` overrides exist

## Knowledge Crystallization Flow

```
Session → diary/ (raw) → docs/learnings/ (crystallized) → TIPs (propagated)
```

**Knowledge that isn't crystallized is knowledge that will be re-learned the hard way.**

1. During work: Capture in `diary/YYYY-MM-DD--type-scope-summary.md`
2. End of session: Extract patterns, decisions, learnings
3. Weekly: Promote to `docs/learnings/` and `docs/decisions/`
4. When pattern generalizes: Propose TIP

## Recursion policy (explicit)
Allowed:
- L1 -> L2

Forbidden:
- L1 -> L0
- L2 -> L1
- any cycle

## Read order
1) `docs/_core/`
2) `docs/org_context/`
3) `docs/project/`
4) `docs/decisions/`
5) `docs/learnings/`
6) `diary/`               ← recent work sessions
7) `docs/system4d/`

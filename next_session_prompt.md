---
summary: "Single-file session handoff to avoid stale status/next-steps docs."
read_when:
  - "At the start of every work session"
  - "When resuming after a pause"
---

# Next Session Prompt

## SESSION TRIGGER (AUTO-START)
Reading this file is authorization to begin immediately.
Do not ask for permission to start.

## ANTI-STALE RULES (HARD)
- Keep this file short and current.
- Keep only the active handoff window (not a history log).
- Do **not** mirror low-level live state that is directly queryable from a DB, CLI, CI, or runtime script.
- If state can be queried, point to the command instead of restating the result.
- Move finished session narrative to `diary/`.
- Crystallize durable patterns in `docs/learnings/` and decisions in `docs/decisions/`.
- Track deferred work in Agent Kernel and keep `governance/work-items.json` as the checked-in projection (not in ad-hoc TODO notes).

## SOURCE-OF-TRUTH MAP
- Repo operating contract: `AGENTS.md`
- Durable direction and product posture: `docs/project/vision.md` and `docs/project/product_posture.md`
- Active/deferred work authority: Agent Kernel work-items state
- Checked-in work-items projection: `governance/work-items.json`
- Explicit task-scope snapshots (when present; frozen exports, not hand-authored truth): `governance/task-scopes/AK-<TASK-ID>.snapshot.json`
- Prior decisions: `docs/decisions/`
- Crystallized learnings: `docs/learnings/`
- Raw session capture: `diary/`
- Queryable live state: runtime commands / DB / CI outputs (reference commands, do not copy snapshots)

## WORK-ITEMS COMMANDS
- Check projection drift: `ak work-items check --repo . --path governance/work-items.json`
- Refresh projection from AK: `ak work-items export --repo . --path governance/work-items.json`
- Legacy JSON bootstrap only: `ak work-items import --repo . --path governance/work-items.json`
- Show explicit task scope (when used): `ak task scope show <TASK-ID>`
- Refresh task-scope snapshot (when used): `mkdir -p governance/task-scopes && ak task scope export <TASK-ID> > governance/task-scopes/AK-<TASK-ID>.snapshot.json`
- Legacy `governance/task-scopes/AK-*.json` files are compatibility-only; do not treat them as primary authored truth.

## SESSION PREFLIGHT (FILL BEFORE EXECUTION)
- Objective (one sentence): Publish and verify the locally completed v0.4.0 standalone decision instrument, then collect the external v1 evidence through its owners.
- Constraints (hard limits): Keep zero core runtime dependencies and the advisory boundary; do not invent host results, AK state, or publication receipts.
- Assumptions (max 3): `docs/project/vision.md` remains durable direction; v2-v4 are outcome ambitions; no vendor-host installation is implied by local tests.
- Blockers (none or list): GitHub integration rejected writes with HTTP 403; the approved live AK runtime/database are outside this environment.

## READ-FIRST ALLOWLIST (STARTUP BUDGET)
1. `AGENTS.md`
2. `README.md`
3. `governance/work-items.json` (projection only; query AK if you need live state)
4. Relevant `governance/task-scopes/AK-<TASK-ID>.snapshot.json` (when explicit task scope is in play; frozen export only)
5. `docs/project/vision.md`
6. `docs/project/product_posture.md`
7. Most recent `diary/YYYY-MM-DD--type-scope-summary.md`

## EXECUTION MODE (ONE SESSION = ONE SLICE)
1. Pick one highest-leverage actionable slice from the AK-backed backlog/projection.
2. Implement end-to-end on a branch.
3. Validate:
   - `./scripts/ci/fast.sh`
   - `./scripts/ci/full.sh` (when CI/policy/ontology/contracts/work-items changed; it runs `fast.sh` first, then heavier checks)
4. Update source-of-truth artifacts before commit, including task-scope snapshots when they are part of the slice.

## SESSION CHECKPOINT (UPDATE BEFORE /commit)
- Slice executed: Standalone v0.4.0 instrument with briefs, sensitivity, revisable evidence, explicit migration, paired reports, verified local MCP and bounded packaging.
- Outcome: Implemented using committed BDD and actual RED checkpoints before GREEN. See `diary/2026-09-07--implementation-standalone-decision-instrument.md` for observed evidence.
- Files changed: Query `git diff 56066fc..HEAD --stat`; canonical source, acceptance tests, generated skill/plugin, packaging and product documentation own the changes.
- Validation commands + results: Re-run `./scripts/ci/full.sh`, the locked optional MCP suite, generated drift checks and clean wheel/archive builds. The diary records observed results rather than live CI status.
- Deferred tasks updated in AK + `governance/work-items.json` exported: Not performed; approved AK runtime/database unavailable. The projection is unchanged.
- Task-scope snapshots refreshed (if applicable): None authored or fabricated.
- Next-session starting point: Inspect `git status` and local commits, obtain GitHub write access, publish the verified head, then read back the remote ref and CI. Preserve the external host evidence gates in product posture.

## END-OF-SESSION
Run `/commit` and ensure this file reflects the real checkpoint for the next operator/agent.

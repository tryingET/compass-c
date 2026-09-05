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
- Objective (one sentence):
- Constraints (hard limits):
- Assumptions (max 3):
- Blockers (none or list):

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
- Slice executed:
- Outcome:
- Files changed:
- Validation commands + results:
- Deferred tasks updated in AK + `governance/work-items.json` exported:
- Task-scope snapshots refreshed (if applicable):
- Next-session starting point:

## END-OF-SESSION
Run `/commit` and ensure this file reflects the real checkpoint for the next operator/agent.

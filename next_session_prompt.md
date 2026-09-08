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
- Objective (one sentence): Complete every accessible vision gate for the v0.5.0 standalone instrument and reconcile the canonical company ontology gate through its owner.
- Constraints (hard limits): Keep zero core runtime dependencies and the advisory boundary; do not invent host results, AK state, or publication receipts.
- Assumptions (max 3): `docs/project/vision.md` remains durable direction; all four horizons now have bounded executable workflows; small local observations do not prove general decision-quality improvement.
- Blockers (none or list): The canonical `tryingET/softwareco-ontology` repository is inaccessible; live AK authority remains outside this environment if an AK-bearing operation is required. No snapshots currently require AK validation.

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
- Slice executed: Implemented bounded v2 evidence batches, v3 portfolios and v4 experiments through BDD, observed RED and GREEN; exercised actual build decisions and fresh installed clients.
- Outcome: See `diary/2026-09-08--implementation-full-vision-dogfood.md`, `docs/project/vision-validation.md`, and retained `evals/` artifacts. The small actual A/A and A/B study does not establish generalized benefit.
- Files changed: Query `git diff 56066fc..HEAD --stat`; canonical source, acceptance tests, generated skill/plugin, packaging and product documentation own the changes.
- Validation commands + results: Query the current ref with `git ls-remote origin refs/heads/main` and current CI with `gh run list --repo tryingET/compass-c --branch main --workflow CI`. The publication diary records observed checks; remote CI does not run `./scripts/ci/full.sh` or establish host usefulness.
- Deferred tasks updated in AK + `governance/work-items.json` exported: Not performed; approved AK runtime/database unavailable. The projection is unchanged.
- Task-scope snapshots refreshed (if applicable): None authored or fabricated.
- Next-session starting point: Inspect `git status`, query the remote ref and CI, then materialize the canonical Softwareco ontology at its actual owner revision once access is available and rerun `scripts/ci/full.sh`. Do not replace missing owner sources or fabricate AK state. Consult actual AK task/direction authority before an AK-bearing continuation.

## END-OF-SESSION
Run `/commit` and ensure this file reflects the real checkpoint for the next operator/agent.

---
summary: "Governance guidance for copier-template / copier / tpl-project-repo / governance."
read_when:
  - "Read when changing or validating generated tpl-project-repo documentation for governance guidance for copier-template / copier / tpl-project-repo / governance."
type: "reference"
---

# Governance

Deferred and active work for this repository lives in the **Agent Kernel DB** (`ak task ...`). The AK DB is the sole work authority; no checked-in projection file exists or should be reintroduced.

## Optional explicit task-scope snapshots

When a repo-local AK task needs explicit scope:

- author/update the scope in AK via `ak task scope show|set|update ...`
- keep repo-side copies under `governance/task-scopes/AK-<TASK-ID>.snapshot.json` as frozen exports
- refresh a checked-in snapshot with `mkdir -p governance/task-scopes && ak task scope export <TASK-ID> > governance/task-scopes/AK-<TASK-ID>.snapshot.json`
- verify checked-in snapshots with `./scripts/check-task-scope-snapshots.sh` before commit or in CI
- treat any hand-authored `governance/task-scopes/AK-*.json` file that is not an AK export as transitional scaffolding, not authoritative truth

## Brownfield migration boundary

If this repo is retiring hand-authored `governance/task-scopes/AK-*.json` files:

- author/update the scope in AK first, then export `AK-<TASK-ID>.snapshot.json`
- keep the legacy `AK-*.json` file only as temporary compatibility fallback while local/CI still depend on it
- remove legacy manifest authoring from workflow docs and handoffs as soon as `./scripts/check-task-scope-snapshots.sh` passes
- if the task still uses repo-default scope, do not invent a snapshot or a replacement legacy manifest

## Non-negotiable

- Do not leave deferred work as ad-hoc TODO comments or scattered markdown notes.
- Do not hand-author `governance/task-scopes/AK-*.snapshot.json` as if it were the live task-scope source of truth.
- Do not reintroduce a checked-in `governance/work-items.json` projection; the AK DB is authoritative.

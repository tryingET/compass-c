---
summary: "Repo-local override notes for the shared engineering-core lane used by this repo."
read_when:
  - "Aligning implementation decisions with the stack baseline for this project repo."
  - "Reconciling local workflow differences with shared lane guidance."
system4d:
  container: "Repo-local deltas on top of shared lane guidance."
  compass: "Keep project work reproducible while preserving local constraints."
  engine: "Use shared lane -> apply local override -> validate with repo scripts."
  fog: "Upstream lane guidance may evolve independently of this repo."
---

# engineering.local (project repo)

Primary lane:

- `py`
- executable upstream retrieval lives in `policy/engineering-lane.json` -> `engineering_core.command`

Default selected disciplines:

- `validation`
- `testing`
- `security-privacy`
- `documentation`
- `dependency-governance`

Executable contract surface:

- `policy/engineering-lane.json` declares the upstream lane reference, retrieval command, catalog/list commands, and selected disciplines.
- `docs/engineering.local.md` records repo-local deltas.
- Repo validation should at least verify the declared lane metadata and may smoke the declared command when available.

Repo-local emphasis:

- This file is the local override layer on top of the upstream lane contract.
- Keep workflow scripts and docs aligned with the declared lane contract.
- Prefer local deterministic wrappers before ad-hoc commands.
- Update this file when local practice intentionally diverges from the upstream lane.
- If the upstream lane ships a conditional `engineering-<lane>.ts-quality.md` addendum and this repo adopts `ts-quality`, keep repo-local rollout truth in `docs/dev/ts-quality-current-vs-target.md` and keep the detailed adoption doctrine upstream in the `ts-quality` repo.
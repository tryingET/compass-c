---
summary: "Ontology Index repo."
read_when:
  - "Read when changing or validating generated tpl-project-repo documentation for ontology index repo."
type: "reference"
---

# Ontology Index (repo)

Start here when browsing manually.

- `ontology/manifest.yaml` — which layers apply
- `ontology/src/system4d.yaml` — repo-local System4D (implementation)
- `ontology/src/reference/concepts/` — repo-local concepts (only when needed)
- `ontology/src/bridge/mapping.yaml` — map concepts to code symbols
- `ontology/dist/` — generated artifacts (tool-first)

Tip: Set `ROCS_WORKSPACE_ROOT=~/ai-society` (or your local workspace root) and use `./scripts/rocs.sh pack <concept_id> --repo . --resolve-refs` instead of opening many files.

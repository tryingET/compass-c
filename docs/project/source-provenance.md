---
summary: "Source and evidence provenance for the initial COMPASS-C implementation."
read_when:
  - "You need to trace the initial design, package lineage, or unresolved evidence claims."
type: "reference"
---

# Initial source provenance

## Operator source

The initial product brief and implementation history came from this public shared conversation:

- <https://chatgpt.com/share/6a9bcb2a-90dc-83eb-a629-34cae8f02623>
- accessed: 2026-09-05
- shared title: `Follow Operating Procedure`

The public page was directly retrievable as HTML. Its visible conversation described the
framework, computational refinement, skill/library/CLI design, skill-engineering pass, and
publication/install sequence. The repository does not contain the raw conversation or private
reasoning traces.

## Reconciled decisions

The conversation contained parallel draft labels and a handoff for a different GitHub identity.
This repository applies the operator's requested ownership and resolves those details as follows:

- repository: `tryingET/compass-c`;
- package: `compass-c`;
- Python import: `compass_c`;
- CLI aliases: `compass-c` and `compass`;
- portable skill name: `compass`;
- release: `0.3.0`, provisional;
- owner and URLs: `tryingET`;
- canonical implementation: `src/compass_c/`;
- generated standalone skill scripts: `skills/compass/scripts/`.

The implementation retains the demonstrated operations—start, get, record, review, invalidate,
and calculate—and the seven bounded calculations: compare, committee, bundle, feedback,
recovery, tail, and Brier score.

## Methodology source

The skill package was revised against:

- repository: `tryingET/procesio-cli`;
- skill: `skills/agent-skill-engineer`;
- locally reviewed version: `2.0.1`;
- locally reviewed on: 2026-09-05.

The development corpus preserves 24 author-visible cases with fixed ordered criterion IDs. It is
not an independent holdout and has not been represented as successful host behavior.

## License source

`LICENSE` is copied byte-for-byte from the local `tryingET/pi-extensions` repository at initial
creation. The text includes a provider rider and must not be described as ordinary MIT.

## Evidence boundary

The shared conversation reported test counts and artifacts from another execution environment.
Those reports informed scope but are not repository proof. Only checks reproduced from this
repository and cited with their actual command output support current implementation claims.

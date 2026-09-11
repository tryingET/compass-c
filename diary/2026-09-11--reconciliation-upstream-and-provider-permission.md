---
summary: "AK 5641 permission update and correction of a stale local-main baseline before further model dogfood."
read_when:
  - "You continue AK 5641 or interpret the interrupted GLM observations."
type: "reference"
---

# Baseline correction and limited provider permission

The operator explicitly confirmed authority to grant limited COMPASS-C inference/evaluation
permission through Zhipu and personal use through OpenAI, excluding training, with a $10
model-evaluation budget. AK evidence 9075 retains that attestation. This does not change
`LICENSE` or independently verify provider retention/training settings.

Pi 0.84.4 reports API-key readiness for `zai/glm-5.3-flash`, using the official Z.AI coding
endpoint. The exploratory harness requested `store:false`, used isolated homes and bounded
local tools, retained final/tool evidence without private reasoning, and reserved conservative
catalog-priced costs before calls. Those request settings are not a legal or provider-policy
verification.

## Controller error: local main was not the current published version

Earlier orientation checked local `main`, tests, and AK but missed the existing `origin/main`
advance. Public readback found v0.6.0 at `92f80c6b20e8cb82e144db96662e45873fac7add`, with 55
commits after the shared baseline; local main contained only v0.3.0 plus this session's two
verified commits. A publication-verified install correctly refused the mismatched skill tree.
No mismatched source was installed or published.

The upstream branch already contains broader runtime features, real paired observations,
saved-workflow dogfood, a seventeen-tool packaged MCP server and declared-source archives.
Therefore old-version observations must not be presented as current-product evaluation.
The original local test evidence remains true only for its recorded commits.

## Interrupted exploratory runs — not completed A/A or A/B proof

- v1 stopped on an SDK auth-return-shape assertion before any model request.
- v2 completed six requests before a pilot turn cap; its synthetic local notebook is retained.
  No comparison was scored and no write was retried.
- v3 froze unchanged source/corpus with a sixteen-request cap and durable sanitized events.
  Fourteen trial records completed before upstream drift was discovered. Some baseline trials
  reached the limit; some skill-enabled trials demonstrably read the skill and finished.
  This partial set was not graded and supports no complete comparison or efficacy claim.
- The owned runner was interrupted on 2026-09-11. Last admitted request 138, for
  `cheap_discriminator-A1`, is effect-indeterminate; its in-flight marker is retained. No retry
  or zero-effect claim is made. Future current-version trials need fresh identities/workspaces.
- Recorded usage across these exploratory runs is about $0.011994. Conservative reservations
  total $0.362198175 and remain charged against the $10 cap, including the interrupted request.

Artifacts remain under `.compass/evaluations/`, excluded from distributions. Uncommitted
prototype scripts/tests and their patch are preserved in
`.compass/evaluations/v0.3-harness-prototypes/`, not shipped as a second evaluation framework.
AK evidence 9094 records the failed baseline assumption and reconciliation prerequisite.

## Next bounded action

Reconcile `origin/main` into local `main` without publication, rewriting history, or dropping
verified local fixes. The same task scope adds only the upstream paths needed for that
prerequisite. `AGENTS.md`, `LICENSE`, and `docs/_core/**` remain forbidden. Reuse the current
release's evaluator and MCP surfaces, validate the merge, then freeze current-version
provider/host tests. Account installation remains a separate actual-user-interface readback.

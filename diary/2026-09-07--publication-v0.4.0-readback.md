---
summary: "Verified source publication, remote CI and commit provenance for v0.4.0."
read_when:
  - "Reviewing publication evidence or relating local implementation commits to public history."
type: "diary"
---

# v0.4.0 publication readback

The operator confirmed that GitHub write access had been enabled. The verified
implementation was published through the authenticated GitHub Git object and ref
APIs. At `2026-09-07T23:31:34Z`, the GitHub API and `git ls-remote` independently
confirmed `tryingET/compass-c` main at
`d839c97b9bc169672c2f25935e770017a0bb5990`. The API also confirmed public visibility
and `main` as the default branch.

The [CI run for that commit](https://github.com/tryingET/compass-c/actions/runs/34170286584)
completed all four jobs successfully:

| Job | Python | Job ID |
|---|---|---|
| Core verification | 3.11 | 101889140730 |
| Core verification | 3.13 | 101889140693 |
| Isolated MCP wheel | 3.11 | 101889140731 |
| Isolated MCP wheel | 3.13 | 101889140523 |

Core verification covers formatting, lint, generated skill/plugin checks, tests,
distribution builds and dependency-free wheel execution. MCP jobs exercise genuine
stdio sessions against the installed wheel. These jobs do not run document freshness
policy, `scripts/ci/full.sh`, AK or ROCS.

## Commit provenance

The API publication recreated author/committer metadata, producing new commit IDs.
Original local commits remain on `local-verified-v0.4.0` and in the previously
delivered Git bundle. Commit IDs in the implementation diary refer to that original
local history; they are not claims about the recreated public IDs.

The implementation tree at original local
`05f8c1bcac82b4dea127744399443e08eb049675` exactly matches published
`93fb6ef38869f730bbfffb20c7f1b71dea48a1ae`. Comparing original final local
`c674c4b982355ebe6ec7b00f1a4a5c6e48db6b9f` with published
`d839c97b9bc169672c2f25935e770017a0bb5990` showed only the product-posture baseline
reference rebound to the published implementation commit. The BDD and RED
checkpoints remain before the GREEN implementation in the published history.

The publication receipt records this observed snapshot. Subsequent documentation
commits may advance `main`; the receipt does not claim to identify a future head.
The prior implementation diary remains unchanged as a record of the earlier HTTP
403 failure and the local checks performed before publication.

## Remaining proof boundaries

Source publication is verified; no release tag, package-registry release, account
installation or vendor-host connection is claimed. COMPASS-C retains zero core
runtime dependencies and provisional maturity. Organization governance checks
remain blocked on the approved AK runtime/database and external ontology
prerequisites. No AK state or projection was fabricated. Controlled host usefulness,
vendor-client adoption and recipient-owned learning evidence remain open.

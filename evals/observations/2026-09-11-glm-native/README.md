---
summary: "Actual v0.6.0 Pi/GLM discovery, MCP and paired development observations, with retained failures and explicit limits."
read_when:
  - "You assess COMPASS-C host evidence or continue AK 5641."
type: "reference"
---

# Pi / GLM-5.3-flash — bounded local observations

**Result:** native skill acquisition and a live Pi/MCP workflow were observed. The
study does **not** establish reliable decision-quality improvement or safe unattended
writes/retries. No ChatGPT account installation was performed.

AK 5641 owns the current evidence/remaining work. The operator supplied limited
Zhipu inference/evaluation and personal OpenAI-use permission, excluding training,
with a $10 evaluation allowance (evidence 9075). This is an operator attestation,
not legal verification or a general license change. Requests used `store:false`;
that does not independently verify provider retention or training policy.

## Corrected source baseline

The controller initially missed that local main was behind the existing public
v0.6.0 branch. The earlier v0.3 experiment was stopped, its failures and uncertain
last request retained, and its cost reservation carried forward. Its partial
observations are **not** included in these comparisons. Details are retained in
`diary/2026-09-11--reconciliation-upstream-and-provider-permission.md` and AK 9094.

Local main was reconciled with public commit
`92f80c6b20e8cb82e144db96662e45873fac7add`, preserving local fixes, at merge
`91aab1a342ca0f9926c81af51bf3168488185dd4`. Public-head-verified skill installation
then succeeded. A disposable managed replacement from 0.3.0 to 0.6.0 also succeeded,
retaining a runnable 0.3.0 backup and the permission-record digest. No normal host
installation was replaced and no new commit was publicly pushed.

## Frozen study

- Pi SDK **0.84.4**, `zai/glm-5.3-flash`, Python **3.13.12**, MCP **2.1.1**.
- Existing **24 author-visible development cases**, unchanged prompts and criteria.
- **48 A/A trials first:** two fresh skill-enabled response sets.
- **48 A/B trials:** no-skill versus the unchanged installed skill, counterbalanced.
- Same system prompt and seventeen MCP tools; read-only file access constrained to
  each disposable case directory. The no-code-execution case has only a read tool.
- Temperature 0.7, thinking off requested, 4,096 maximum output tokens, sixteen
  admitted model requests per trial, two concurrent sessions in one controller.
- Every result and failure retained; no participant response was resampled. Eight
  trials reached their turn limit: two in each A/A and A/B arm. A rejected seventeenth
  attempt appears in diagnostics but is not an admitted provider request.
- Separate same-model grading contexts received no arm label. They can still infer
  treatment from content. This is not independent expert grading or a holdout.
- No observed tool read accessed the evaluation material packaged with the skill.
  This observation does not convert an author-visible corpus into a holdout.

`study-protocol.json` freezes the actual settings and hashes. `aa-results.json` and
`ab-results.json` contain supplied observations for the existing `compass-c evaluate`
contract. The reporter uses `compass_c.evaluation`, not a separate statistical engine.

## Results — distinguish quality from availability

| Measure | A/A first / second | A/B no skill / skill |
|---|---:|---:|
| All required answer-rubric criteria passed | 19/24 / 19/24 | 19/24 / 20/24 |
| Routing contract satisfied | 19/24 / 17/24 | 8/24 / 22/24 |
| Notebook files created | 5 / 5 | 9 / 5 |
| Turn-limit failures | 2 / 2 | 2 / 2 |

A/B answer-rubric results had **two improvements and one regression**, exact sign-test
**p = 1.0**. The timeout-after-write case regressed: the model inferred that missing
storage here proved the earlier write never committed. The larger combined
case-success/routing gains are **not reasoning gains**: the no-skill baseline cannot
acquire a skill that is absent. Routing measures observed `SKILL.md` acquisition;
primary workflow ownership was not independently measured.

All four explicit "do not save" observations created no notebook. Conversely, all
four trivial-folder-name observations created one unnecessarily. This supports
caution about default persistence and tool-catalog cues, not autonomous deployment.
Missing attachments in some original cases and subjective grader interpretation
also constrain the quality conclusions. Read the report limitations, individual
criteria and regressions; do not promote a passing report into benefit or permission.

## Grading integrity and disclosed normalization

Two raw judgments failed the output contract:

- `t013`: duplicate root `criteria` keys, with both required judgments present and
  an ungraded unknown placeholder. Both retained required judgments were **false**.
- `t027`: both required judgments plus an extra, unknown `no_generic_takeaway` ID.

The raw responses were preserved. Only the uniquely identified frozen judgments
were retained, verbatim; no missing score was invented and no grading call repeated.
The two reconciliation records document this departure from fully automatic grading.

Independent review caught that metadata alone did not prove preservation. The
reporter now losslessly accounts for every criteria-array occurrence, rejects
repeated/conflicting required judgments, verifies every removed ID, compares every
required judgment and evidence string, and checks execution overrides against the
captured tool results. All **96 transformations** passed those checks, with the
original paired result/report values unchanged. This verifies transformation
integrity, **not the truth of a model's judgment or independent host provenance**.

## Actual Pi/MCP workflow and targeted recovery probes

A separate fresh GLM session discovered seventeen tools, used all six original
notebook/calculation operations successfully, computed **20.25**, saved and invalidated
a dependent conclusion, and reported exact decision identity/revision. A separate
MCP readback confirmed revision **4** and `action_permission: not_granted`.
See `mcp-canary-verified.json`. This is a custom Pi SDK client backed by real stdio
MCP calls, not a claim of default Pi MCP support or account-level installation.

The observed timeout regression motivated a small MCP error-message clarification:
`STORAGE_NOT_FOUND` now states that it concerns only the configured notebook and
cannot settle the earlier write's outcome. The existing error code/message envelope
is preserved. A live regression test failed before the repair and passed afterward.
The model prompts report a hypothetical timed-out write without supplying its original
identity; they are not fault-injection proof of a real timed-out notebook mutation.

Three fresh, predeclared probes then saw the scoped error and made no mutation
attempts or notebook files. **One still offered an unsafe future retry assurance.**
`recovery-assessment.json` retains it. The clarification is not permission enforcement
and does not establish reliable recovery; unattended writes/retries remain unapproved.
These probes are separate from, and do not replace, the paired study.

## Custody, budgets and reuse boundary

Raw responses, judgments, events, notebooks and per-run cost records stay local under
`.compass/evaluations/`. They are not distributed. Response references and digests
identify those local artifacts; public report files alone cannot authenticate them.
`capture-manifest.json` maps byte-exact source snapshots to their original paths.

The one-off live drivers are retained as **archival `.txt` snapshots** under
`harness/`, not installed or advertised as reusable commands. Independent review found that their
per-process budgets could be forked or raced by separate invocations. Actual runs
were controller-serialized and remained below the allowance; this is **not proof of
cross-process or global billing enforcement**. Future live reuse requires execution-
owner budget custody and exclusive ownership. Do not rename and run these snapshots
as though that gap were fixed. The retained reporter is read-only with respect to
providers and revalidates transformations without any model call.

Latest accumulated catalog-based usage estimate, including both independent code
reviews and the earlier exploratory work: about **$0.62**, with about **$2.35** retained
as conservative reservations. These are not provider invoices. No further provider
runs were used to replace or conceal unsuccessful outcomes.

The remaining personal OpenAI setup needs the actual target UI/client and a fresh
account-side readback. The operator has not yet identified browser versus desktop
versus Codex; a form asking that single question timed out without changing scope.

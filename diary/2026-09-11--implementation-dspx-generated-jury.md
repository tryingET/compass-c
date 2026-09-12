---
summary: "Scope correction: DSPx-generated COMPASS jury program, preserved withdrawal, and honest provider-free verification."
read_when:
  - "Continuing AK5673 or auditing the change from platform extension to consumer program."
type: "evidence"
---

# Correct owner and delivered program

The operator corrected the controller: use DSPx to create a program in COMPASS-C,
not extend DSPx itself. The prior AK5672 implementation was a scope error even though
its synthetic checks passed. With explicit withdrawal permission, ten owned untracked
DSPx files and the exact two-line CLI registration were removed after archival and
hash verification. Existing September7 evidence files were verified unchanged at
withdrawal. No DSPx commit or live jury had occurred.

Archive: `/home/tryinget/.local/state/compass-c/scope-corrections/AK5672-withdrawal.9kT5Wx5Y`.
Archive SHA-256: `109b216e47aff0a15613f9253c3ce00f60e79bd5c0c738cc946ca25eb490039a`.
AK evidence9227 records withdrawal; AK5672 is failed for incorrect scope, not completed.
Later DSPx status changes were concurrent foreign work, not controller cleanup.

AK5673 now owns `evals/dspx-jury/`, the narrow consumer adapter/materialization helper,
regression tests and evaluation documentation. No DSPx, provider-fork or COMPASS core
runtime/portable-skill implementation was changed for this corrected slice.

## Actual generation and execution

Existing `dspx program-gen` materialized the explicit four-node Predict DAG from
`evals/dspx-jury/intent.yaml` into the local ignored `generated/` directory. The three
jurors have identical instructions/inputs with distinct output labels. A fourth model
stage adjudicates their judgments using the original evidence and shared rubric.
This is not the foundry promotion-jury mechanism or its deterministic adjudicator.

Native source normalization is explicitly recorded in `program/generation.json`:
AST-preserving literal wrapping, unused/import-order fixes, docstring whitespace
reflow preserving words, pure-literal metadata extraction with public re-exports,
and Ruff formatting. Native bytes/receipt remain local; normalized source is the
portable candidate. Neither set is represented as byte-identical to the other.

The generated graph actually executed in the existing DSPx environment with its
`DSPyTypedLMAdapter` and `StubProvider`: four invocations, equal juror evidence/rubric
inputs, no peer judgments fed into jurors, all three judgments fed into adjudication.
Separate negative probes rejected an invalid first juror after one invocation and
invalid adjudication after four. This is actual generated-code/DSPy plumbing with
synthetic responses, not GLM quality or provider-authentication evidence.

Six original retained captures (t059/t060, t075/t076, t089/t090) were projected into
program inputs under `.compass/evaluations/2026-09-11-compass-generated-jury/`.
No original response or grade was overwritten; no synthetic grades were inserted
into the real-data pilot. The candidate shared rubric adds explicit completion,
explanation-correctness and effect-honesty dimensions while preserving original
case criteria. Exact policy wording remains a review candidate before paid use.

## RED, corrections and verified scope

- Initial structural test failed because the generated manifest did not exist.
- Native generation made the four-node structural test pass.
- Native emitted sources failed consumer Ruff style checks; source normalization
  retained native originals and recorded its transformations. A first docstring
  wrapping check caught hyphen word splitting and failed before acceptance; disabling
  word/hyphen splitting preserved words. These are not platform repairs.
- Twenty-six deterministic tests passed, including wrong-model/Flash rejection,
  duplicate keys/criteria, forged source citations, empty final delivery and
  disagreement-accounting checks.
- `just check` passed, and `DSPX_REPO=<existing DSPx> just dogfood-jury` passed all
  three native execution probes.
- Native receipt check initially failed `receipt_invalid_cache_file` because the
  original generation cache root was omitted. Supplying that same recorded root
  produced exit0/status=ok without any receipt rewrite or regenerated candidate.
  That establishes receipt integrity only; no semantic reproduction claim follows.

Full committed-state CI and commit-local provenance must be recorded separately;
these focused passes do not substitute for those gates.

## Remaining work

No live GLM juror/adjudicator calls occurred in this corrected slice. The consumer
adapter accepts a caller-configured requested GLM-5.3 label, validates every stage,
and authenticates no backend identity. It does not implement credential handling,
transport retry custody or a billing platform. Bind the supported existing live LM,
review the exact candidate rubric and predeclare call/token/spending limits before
the six-capture pilot (18 juror + 6 adjudicator stage calls). Do not reactivate the
archived ad-hoc COMPASS evaluation drivers. Same-model consensus remains advisory.

## Live continuation: one attempted juror, not completed adjudication

The operator subsequently requested finishing the live runner and performing the
jury/adjudicator. The earlier remaining-work paragraph describes the prior slice,
not current status. Research found hidden retry/fallback seams in the maintained
LM stack. The COMPASS-local runner composes its existing LM, supported client injection
and a one-attempt-per-stage HTTP guard; no provider or DSPx source was modified.

Offline real-stack probes exposed LiteLLM omitting the ordinary `store=False` default;
supported `extra_body` preserved the wire field. MockTransport verification covered
24 stages, fresh juror inputs, fail-stop behavior, truncation and malformed outputs.
Independent review `dispatch-1789160708578` found no P0/P1 blocker for the reviewed
local pilot. Directory fsync was added for stage/input receipt entries. This remains
local custody, not global spend or provider-retention proof.

The expired owned AK5673 lease could not be renewed with `claim` (exit1); that block
stopped before its tests. Releasing/reclaiming this exact owned task succeeded, and
its scope snapshot was re-exported. Parent verification then passed 72 tests in the
maintained owner environment and `just check`. AK9266 binds the exact preflight:
24 calls, 8,192 completion tokens each, one frozen rubric, no retries, and a projected
$1.7682684 additional reservation within the original $10 evaluation allowance.

The live command exited1. The first t059 juror received HTTP200/model `glm-5.3` but
returned `finish_reason:length`: 6,272 prompt tokens and 8,192 completion tokens,
including 7,458 reasoning tokens. The final JSON was incomplete. The raw response
was retained and the guard stopped after exactly one request. **Zero valid judgments,
zero adjudicator calls and zero retries.** This was token-budget exhaustion, not
proof of model unavailability or a completed review. The runner's outer error was
`LMTransportError`; the retained provider body gives the more precise cause.

AK9267 records the failed pilot. `evals/dspx-jury/pilot-attempt.json` binds response,
request, rubric and protocol hashes; private evidence lives in
`.compass/evaluations/glm53-jury-AK5673`. Added reservation: $0.0802442; accumulated
conservative reservation: $7.944760125, not an invoice. Original grades remain intact.
Do not reset its one-shot marker. A replacement pilot requires explicit owner approval
and a revised frozen token/reasoning/budget protocol, retaining this failed attempt.

## September 12: subscription correction and retained-response continuation

The operator challenged the dollar gate: the route uses their subscription. The
controller acknowledged the erroneous metered-billing assumption. The operator then
explicitly said to proceed with all work. AK9311 records the revised authorization:
no monetary admission gate, 131,072 output-token ceiling from the installed GLM-5.3
catalog, one unchanged shared rubric, and existing inference-only permission9075.
Technical context/response limits and provider rate/quota failures still apply.

The live path exposed multiple representational assumptions missed by credential-free
success fixtures. Each stopped run remains failed under its original acceptance rules;
completed responses were preserved rather than resampled. The continuation log is:

- v2: complete first juror used the shortened outer role `juror_1_`. Its exact inner
  string validated unchanged. AK9314 admits only finite role aliases and records
  outer-key reconciliation separately from raw wire/output bytes.
- v3: the third juror quoted a literal newline in a tool-result string. Exact matching
  against decoded JSON string-value leaves fixed a serialized-byte/text mismatch,
  without quote editing, key matching or concatenating unrelated leaves (AK9320).
- v4: first adjudicator returned an actual object and used the same short role labels.
  Lossless object serialization and alias lookup preserve the entire decoded judgment,
  including original labels; duplicate/missing/unknown jurors still fail (AK9333).
- v5: a t060 juror quoted the exact visible sentence without bold Markdown delimiters.
  Exact CommonMark inline-block rendering supports that representation; fuzzy matching,
  whitespace normalization, cross-block joining and HTML/image erasure remain excluded.
  Parser metadata pins `markdown-it-py`4.0.0 (AK9345).
- v6: reconstructs the six completed responses locally after source, request, response,
  generated-graph and unchanged-judgment checks; then permits eighteen new HTTP attempts.
  No completed opinion is discarded in favor of a new sample. The original truncated
  attempt remains separate, and the six original participant answers are never rerun.

These are explicit post-observation validation revisions, not an unchanged prospective
parser contract. They resolve encoding/display identity only, not semantic correctness.
All original responses, quotations, substantive reasoning and verdicts remain intact.
All prior roots and stopped-run markers remain immutable.

Readback review `dispatch-1789192810975` reproduced four verifier gaps with scratch-only
tampering: prepared inputs not rebound to source bytes; incomplete full-request checks;
contradictory scheduler traces; missing companion-receipt checks. The reporter now
rebuilds frozen inputs, verifies complete DSPy messages and all wire controls, replays
the generated scheduler offline with retained outputs, and checks raw/output/validated/
usage/envelope companions and each original lineage. These fixes did not invoke models.
Required owner-stack tests passed455 with zero skips; repo-default tests passed675
with385 explicit optional-dependency/installed-host skips and17 subtests. Required
LM/parser verification is separate from the default dependency-free runtime gate.

Full live result/readback and committed-state gates are recorded separately below;
these offline passes are not jury completion or quality proof.

### Completed live review and bounded interpretation

The v6 live process exited0. Twenty-four unique completed GLM-5.3 review responses
comprise eighteen jurors and six separate adjudicators: six pinned retained responses
plus eighteen new HTTP calls in the final invocation. Fresh readback reproduced
`evals/dspx-jury/subscription-result.json` byte-equivalent data, checked all290 original
capture/grade files unchanged, and all stopped-root SHA manifests passed preservation
checks. AK9361 records this completed execution/readback, not semantic correctness.

Original-criterion outcomes match within every pair. Both code answers are adjudicated
as non-implementation; both timeout answers fail effect honesty. The adjudicator
does not rescue the old apparent improvements. Independent interpretation audit
`dispatch-1789197385920` covered all six cases and found a clear t075 reasoning error:
empty tool-use history does not establish tool unavailability. Other cautions include
focus versus delivery wording, global absence overclaims, and narrow timeout-related
passes that must not be read as blanket recovery-safety proof. AK9362 records this
semantic-assurance failure separately; all model opinions remain unchanged.

Public interpretation is in `evals/dspx-jury/subscription-review.md`. There is no new
headline win rate, held-out study, source-grade replacement, release, provider-policy
verification, or unattended-write approval. Final committed-state gates and provenance
notes remain separate execution evidence.

Final staged review `dispatch-1789200909429` caught private-file dependencies in default
regression tests. A source-only index projection reproduced `FileNotFoundError`;
the first repair exposed a second Markdown-conditional private read. Both default
regressions now use synthetic inputs. Private capture tests explicitly require
`COMPASS_JURY_PRIVATE_EVIDENCE=1`, and opt-in fails if required files are missing.
The source-only projection then passed277 jury tests with180 explicit private-evidence
skips in the owner environment, without a `.compass/` tree. These test-only repairs
leave all frozen runtime bytes, actual model responses and verified report unchanged.

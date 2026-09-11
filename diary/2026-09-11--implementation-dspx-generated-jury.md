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

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

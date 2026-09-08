---
summary: "BDD, RED/GREEN and observed use of the saved v4 experiment workflow."
read_when:
  - "Reviewing the persisted experiment lifecycle and its evidence boundaries."
type: "reference"
---

# Saved experiment lifecycle

The user asked to continue making the v4 vision real and to dogfood during the
build. The prior package version 0.5.0 is an implementation checkpoint, not the
vision's final horizon. A read-only design review identified the missing link:
experiment calculations were transient and required manual transfer into notes.

The accepted design keeps an immutable experiment plan and its single observation
in the existing notebook. It binds the model to declared evidence dependencies,
allows a fresh process to resume it, previews observations without writing, and
atomically retains the prior and posterior while invalidating dependent reasoning.
An explicit event identity makes an identical lost-response retry idempotent.
It cannot identify relabeled copies of the same underlying evidence.

Schema 3 is explicit. New notebooks use it; old schema-1/2 records retain their
existing operations and require `migrate` for the new workflow. Neither a read nor
starting a decision in an existing notebook silently migrates it. A plan supports
one observation; a subsequent experiment requires a new plan and likelihoods
appropriate to accumulated evidence.

The prospective local dogfood protocol is retained in
`evals/dogfood/v4-lifecycle/protocol.md`. The earlier 91-command exercise is a
documented friction signal, not a matched baseline for this workflow. At revision
17, build decision `3f244e36d35e410b9cd36bb353a1771c` explicitly records that limit.
Actual observed artifact-check output must supply the new experiment's result;
successful plan creation is not an observed pass.

This work does not change Softwareco's ontology ownership. `softwareco/ontology`
is the consumer workspace path. Its current submodule declaration points to
`tryingET/softwareco-ontology`, for which the connection returned 404; that does
not establish whether the backing repository is private or was never published.
No obsolete tree or fabricated scope is substituted to make governance green.

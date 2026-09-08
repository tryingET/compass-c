---
summary: "Actual v0.5 installed-client exercise, retained command evidence and usability costs."
read_when:
  - "Checking what the final local client exercise actually executed and observed."
type: "reference"
---

# Installed-client use completed, with substantial capture and readback overhead

A fresh Work Mode agent used the dependency-free installed COMPASS-C 0.5.0 CLI
to reassess the integration-review sequence. It received the sanitized portfolio
model and prospective experiment inputs, normal skill guidance and references,
and no prior output fixtures or expected answers. Its actual user-facing result
is retained in `final-brief.md`.

The client calculated portfolio, experiment and probability-sensitivity results,
created its own notebook, recorded observed command evidence, previewed a
revision without writing, explicitly applied it, and reconsidered dependent
conclusions. Preview preserved revision 14, identical get output and identical
database bytes. Apply advanced to revision 15; the final readback reached
revision 24 and retained eight stale notes. Decision ID:
`5a85299b44644a99ba292b80383fd9dc`.

The brief conditionally recommends the three prerequisite reviews before
integrated paths, while preserving the distinct modeled role values and their
common optimum. It does not invent real stakeholder agreement. The independent
32-model experiment was **not executed in this exercise**; calculator success
was not relabeled as its pass observation, and the original illustrative prior
remained unchanged. This scope does not contradict separately retained earlier
experiments that were intentionally unavailable to this participant.

## Observed cost and friction

| Captured target subprocesses | Count |
| --- | ---: |
| Setup, guidance/input/package reads and help | 9 |
| Calculations | 3 |
| Notebook creation, recording and update preview/apply | 25 |
| Notebook get/brief readbacks | 54 |
| Total | 91 |

All 91 captured target subprocesses exited successfully. These are actual
commands, not 91 distinct decisions or a measure of benefit. Fifty repeated
`get` commands account for much of the cost: the exercise deliberately read
current revisions before writes and inspected the resulting records afterward.
Setup, capture-driver launches and host tool wrappers add orchestration beyond
these target counts; the trace is not a complete count of host interaction.

`usability.json` preserves the participant's observations. `record --help` did
not enumerate supported kind/status values or the default status, so discovery
required an empty brief and a note readback. Calculator schemas required the
references. Full portfolio display was truncated by the host, while complete
stdout remained available in the retained output. Evidence clarification caused
dependent notes to become stale and required explicit reconsideration. These
costs remain visible; no command failure or correction was erased.

The initial read-only `cat` of the task preceded the controlled capture driver;
the participant disclosed that bootstrap environment/capture departure. The
trace retains exact argv, exit status, stdout and stderr for every target command
subsequently launched through the driver, including every installed CLI call.
Outer host wrappers are not reconstructed as additional exact traces.

## Version and evidence boundaries

The actual installed package path, version and command outputs appear in
`command-trace.json`. The wheel used for this exercise has SHA-256
`9f8241fb1bccacc9841212e392141a7516c8c5a7a68c52cac5b6e27aaad8ce72`;
the supplied skill has SHA-256
`09e26a8cb61167be937c581d21daf8e0286ba644137bbc523750a4db346d200a`.
`manifest.json` retains hashes of the guidance and raw inputs as well. Later
edits or rebuilt wheels are not byte-identical to this recorded treatment.

The manifest's original `source_commit` is a **local** commit identifier and is
preserved unchanged. The parent publication mapping identifies remote commit
`309fe48ed09438900c91bfb96d53321800b2c93a` as preserving that source tree; GitHub
commit metadata changed the identifier. Neither identifier substitutes for the
recorded wheel and skill hashes.

This is actual author-visible local installed-client use. It is not native
vendor discovery, an independent holdout, comparative behavioral improvement,
measured real-world usefulness, stakeholder authorization or completed product
vision. `record_complete_not_verified` records structural completeness only.

## Capture preservation

`capture-script-map.json` maps each original executed `.py` filename to its
archived `.py.txt` filename and byte hash. Renaming preserved the exact executed
bytes instead of formatting historical capture scripts to satisfy source lint.
Command traces intentionally retain original names. These scripts are evidence,
not supported reusable tools; replaying them against the existing notebook can
change its history. The canonical `experiment-partner.py` outside this exercise
was not renamed or changed.

The raw models, trace, output envelopes, preview checks, apply/readback records,
final notebook brief and usability report remain unchanged by this archival
step. The task-owned database is local execution state; inspectable JSON
readbacks preserve the observed state alongside this readout.

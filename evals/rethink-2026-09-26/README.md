---
summary: "Retained evidence for the 2026-09-26 rethink: independent critic briefs and outputs, the measured claim guard, natural-use classification and risk-reproduction probes."
read_when:
  - "Checking the evidence behind the 2026-09-26 rethink report or the pause decision."
  - "Reproducing the saved-plan brittleness, read-cost or payload-limit findings."
type: "reference"
---

# Rethink evidence, 2026-09-26

The files here support the [frozen frame](../../docs/decisions/2026-09-26-rethink-frame.md), the [probe report](../../docs/decisions/2026-09-26-rethink-probe-report.md) and the [pause decision](../../docs/decisions/2026-09-26-adr-pause-discretionary-expansion.md). They were produced in session scratch space and retrieved into this directory the same day. Hashes for the byte-identical files match the ones the report recorded.

## Independent critique (`critique/`)

Three separate Pi runs of `openai-codex-2/gpt-6-astra`. Each had read-only tools, no skills, no context files, and only the provider extension loaded. `run-metadata.json` gives the exact invocation, packet digests, exit codes, reported models, usage and event-stream digests.

| Run | Brief | Output (SHA-256 prefix) | Role |
|---|---|---|---|
| A | `A-brief.md` | `A-final.md` (`db13761f`) | Blind re-scoring of P1/P2 and probe 2; did not see the report |
| B | `B-brief.md` | `B-final.md` (`b192e58e`) | Critique of the argument; recommended E\* |
| C | `C-brief.md` | `C-final.md` (`a1e84a93`) | Adjudication of the guard's 20 flags at HEAD |

`*-final.json` holds each run's structured verdict block, as extracted by `extract.py.txt`.

The critics received read-only packets: a HEAD repository snapshot, exported commit diffs, 34 AK evidence exports and probe-2 data. **The packets and raw event streams were not retained.** The packets duplicated the repository, and both they and the event streams contained verbatim excerpts of the operator's prompts from other sessions. Including those excerpts contradicted the frame's counts-only rule. The critic outputs paraphrase those prompts and do not quote them.

## Measured claim guard (`guard/`)

| File | Contents |
|---|---|
| `check-claim-freshness.py.txt` | The prototype guard (`f0e4d4db`), archived as non-executable text under the pause |
| `protocol.json` | The measurement protocol (`1c87219d`), frozen before any run on the repository |
| `head-flags.json` | The guard's output at HEAD 23f883d |
| `history-counts.json` | Flag counts at every first-parent commit |
| `ak-evidence.json` | The AK input used: evidence ID, task, and time checked |

Results: 43–50% recall and 25% precision (critic C). See the report's addendum.

## Natural use (`natural-use/`)

- `classify.py.txt` is the session-log classifier.
- `classified.jsonl` holds per-session counts. It contains no conversation content.
- `probe2-data.redacted.json` is the probe-2 export with the operator's prompt excerpts removed before publication.

## Risk probes (`risk-probes/`)

These reproduce the review's verified runtime risks. Run them from the repository root, for example `python evals/rethink-2026-09-26/risk-probes/probe_brittle.py.txt`. Each creates disposable notebooks under the system temporary directory and does not delete them.

| Probe | Observed on 2026-09-26 |
|---|---|
| `probe_brittle.py.txt` | Changing only `experiments._LIMITATIONS` wording makes `experiment` and `brief` fail with `INVALID_STORAGE` for a decision with a saved plan |
| `probe_perf.py.txt` | `brief` took 8 / 46 / 178 / 469 ms with 1 / 10 / 40 / 100 saved plans (8×8 model, 300 notes). This timing is machine-specific. |
| `probe_big.py.txt 4 8` | For a 64×128 model: `calculate` 0.51 s, plan write 1.04 s, `brief` 0.51 s |
| `probe_big.py.txt 16 16` | `calculate` 3.6 s. `plan_experiment` fails with `INPUT_TOO_LARGE`: the 1 MB stored-proposal limit is smaller than the calculation's documented bounds. |

These observations are local diagnostics, not a performance specification.

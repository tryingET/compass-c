The resume task completed through the installed CLI. No target subprocess failed, timed out, or required a retry. The actual check ran once; preview ran once; apply ran once. No result was supplied in the handoff or substituted from a calculator/notebook command.

Discovery worked from the notebook path and decision ID: `experiments` returned the pending plan and protocol, and `experiment --full` recovered the complete model, likelihoods, provenance, assumptions, bounds, and revision. The documented executable aliases resolved successfully. The capture helper exposed a 30-second parent timeout, removed `PYTHONPATH`, and set `PYTHONDONTWRITEBYTECODE=1`; its source was read only to verify that interface before execution.

Observed usability friction:

- Full readback repeats the model, protocol, and limitations across stored parameters, proposal, and update. This preserves audit context but adds substantial reading volume.
- The generic `brief` reports `needs_work` and empty recommendations, alternatives, and reversal conditions after a successful observation lifecycle, while its experiment summary exposes the current winner. A reader must distinguish persisted arithmetic from a fully authored decision brief.
- The brief retains the preparation-stage constraint to leave the experiment pending even after the authorized resumer has completed it. The current task explicitly authorized the resume operation; this historical constraint was left intact.
- A read-only final `experiment --full` embeds an observation receipt with `replayed: true` and `applied: false`. This is readback presentation, not a second apply attempt. The actual apply capture is `observation-applied.json` and records `applied: true`, `replayed: false`.
- Independent no-write auditing requires external storage-byte checks; CLI success alone does not provide that proof. Both checks retained database size/hash and absence of WAL, SHM, and journal sidecars.

Execution details and limits: the actual check path was expressed relative to the fixed authorized working directory, as permitted by the task. All target subprocesses and permitted text reads used the capture helper. Observation/event JSON and these final Markdown files were written directly with the provided file-edit tool within the named evidence directory; no target subprocess was used for those edits. No repository source/history, original model-input file, preparer's outputs, prior dogfood artifacts, or grading material was inspected. No delegation, installation, browsing, external action, or additional experiment occurred.

The helper records requested and resolved target argv, alias mapping hash, process identity, and observed timing. The outer host's complete wrapper argv and process details are not exposed by the execution tool; they were not reconstructed. The check's reported zero child processes and zero writes are retained as its output, not presented as independently audited host behavior.

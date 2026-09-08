Usability and departure notes

- All target commands completed successfully. No failed command, timeout, lost response, retry, or unexpected write outcome occurred.
- Installed identity was captured: COMPASS-C 0.6.0 from the isolated v0.6-core Python environment.
- The plan write with --full returned saved inputs, decisive arithmetic, state, and IDs together; no immediate notebook readback was needed. Returned revision 1 from start was used for the plan write, which returned revision 2.
- Evidence-directory placement was abbreviated in the task as run-3/prepare; reading the allowed capture helper resolved its exact location.
- Generic notebook guidance mentions locating a scripts/compass.py path, while the task supplies frozen installed entrypoint aliases. The task-specific aliases were used successfully.
- Capture records retain requested and resolved target argv, target outcomes and timestamps, environment controls, and the driver process fields exposed by the helper. Additional host-wrapper internals are not exposed by the tools and were not reconstructed.
- Work was limited to the supplied task, four allowed guidance files, parameters, allowed capture helper, installed identity/help, own outputs, the named notebook, and prepare evidence. No experiment execution, observation, delegation, installation, repository-source/history inspection, or protocol/grading inspection was performed.

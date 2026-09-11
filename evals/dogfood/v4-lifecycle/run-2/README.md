---
summary: "The corrected guidance removed extra readbacks; a captured path typo still failed the effort gate."
read_when:
  - "Assessing the second lifecycle run and its measurement-harness remediation."
type: "reference"
---

# Run 2: eight successful operations, nine attempts

Two new fresh participants completed the same saved-plan, cold-resume, actual
check, preview, apply, and brief task under the repaired guidance. The preparer
used `plan-experiment --full` directly. The resumer relied on its recovered
revision, preview response, and unchanged complete storage bytes without extra
state reads. This removed the three additional product readbacks seen in run 1.

The frozen gate still **failed**: nine product attempts exceeded eight. A mistyped
absolute executable path prevented one plan command from launching; its exact
argv, `FileNotFoundError`, and corrected attempt remain captured. Eight actual
product operations succeeded. The failed attempt was not removed from the count
or reclassified to make the gate pass. Seven other rubric checks passed.

| Captured target attempts | Count |
|---|---:|
| Product attempts, including one launch failure | 9 |
| Help | 5 |
| Setup and observation-file preparation | 3 |
| Actual experiment | 1 |
| Evidence verification | 3 |
| Total attempts | 21 |

Twenty target processes launched and all exited successfully. Fourteen recorded
guidance/input reads and 35 capture-helper invocations are separate. A resumer
helper-path typo caused another wrapper failure before capture or a target
process could start; its exact exposed command and error are retained in
`resume/uncaptured-wrapper-failure.json`. Unknown host process details are not
reconstructed. The largest default workflow response was 3,838 UTF-8 bytes.

The actual check ran once in this attempt, passed all three finite cases, and
made 11 public calculator calls. The source observation was 410 bytes; the
unchanged original input was 2,846 bytes. Total captured target-attempt time was
approximately 0.86 seconds, excluding agent work and outer orchestration. The
repeated check is not independent reliability evidence and its illustrative
posterior is not combined with the first run's posterior.

## Direct state and receipt verification

The controller independently compared the initial full write response, recovered
plan, and final lineage against the frozen parameter file. They match. The known
revision and preview response both report 2. Database bytes and the presence or
absence of rollback-journal, WAL, and SHM sidecars match before and after preview.
One explicit apply advances to revision 3.

The final generic brief contains exactly one current observed outcome. Its ID,
source, and content match the apply receipt and retained observation. The full
plan's embedded receipt says `replayed: true`, `applied: false`; it is a readback
of the recorded event. The command trace contains exactly one apply attempt,
whose original receipt says `applied: true`, `replayed: false`. No second
observation was applied.

The participant's final brief conditionally favors integration review, preserves
further review as the alternative, identifies the actual source, and states a
reversal threshold and model limits. The generic notebook brief's narrative
categories remain empty and its structural status remains `needs_work`; this
limitation was disclosed rather than hidden with additional writes.

## Integrity and next correction

Decision: `6274b21cddee461692b687992ccb8d69`. Plan:
`8851a5935fd44ce3a21c4be95f360161`. `assessment.json` retains the ordered checks,
failure, metrics, and receipt audit. All frozen inputs, the wheel, and the skill
were unchanged through completion.

`frozen-inputs/` preserves this attempt's exact inputs and capture helper. Its
complete skill treatment is reconstructed from `../run-1/skill-snapshot/` with
the two corrected references replaced from `skill-snapshot/`; every expected
file hash appears in `manifest.json`. No runtime or wheel change was made.

The next correction belongs to the capture helper: explicit executable aliases
and a short driver path remove repeated transcription of long installed paths.
The helper must retain requested and actual argv, reject missing alias mappings,
and preserve unknown paths and failures without automatic correction or retry.
This is measurement-harness ergonomics, not an additional product feature or a
rescued pass for either failed run. Acceptance thresholds remain unchanged.

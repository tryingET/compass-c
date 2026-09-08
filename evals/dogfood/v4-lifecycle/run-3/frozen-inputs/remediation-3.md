---
summary: "Prospective capture-helper repair after repeated absolute-path transcription failures."
read_when:
  - "Checking the third lifecycle run's narrow measurement change and fixed acceptance."
type: "reference"
---

# Run 3: exact executable aliases in the capture helper

Run 2 preserved eight successful product operations and one failed product-launch
attempt. The latter caused its fixed eight-attempt gate to fail. Both earlier
runs also retained a helper-path typo before a target process could start. These
are concrete capture ergonomics defects; neither failed result becomes a pass.

The new helper accepts only two explicit aliases at target argv position zero:
`compass-c` and `installed-python`. It resolves them from the frozen manifest's
`installed_cli` and `installed_python` paths. It records requested argv, actual
launch argv, current working directory, mapping key, and manifest hash. Other
arguments and unknown strings are untouched. Missing mappings fail; there is no
fuzzy correction, automatic retry, result inference, or failure suppression.
The implementation is protected by its BDD, failing-test, and passing-test
checkpoints and focused regression tests.

Participants call the helper by a short repository-relative path with the exact
repository working directory. The helper's Python interpreter only captures
commands; product and check aliases still launch the byte-identified isolated
installed environment. Optional short database/input arguments name the same
authorized files relative to that working directory. The helper does not rewrite
those arguments or expand participant permissions.

Use one new fresh preparer/resumer pair, a new task-owned notebook, and `run-3/`
evidence. The semantic tasks, candidate wheel/runtime, ordinary skill guidance,
input model, actual check, and every ordered rubric criterion remain unchanged
from run 2. The participant tasks add only the explicit capture interface and
working-directory instructions. They contain no grading rubric, expected result,
previous participant output, or favorable command-count hint.

Freeze this remediation, tasks, helper, manifest, and unchanged inputs before
launch. Retain every target attempt, alias-resolution failure, wrapper failure,
help/setup call, actual check, and evidence-verification cost. Failed attempts
still count. A further failure requires a separately identified diagnosis and
remediation; do not quietly rerun this pair or choose only a favorable result.

The local check executes once more as part of the unchanged complete task. Count
the additional execution and do not treat repeated checks of the same artifact
as independent reliability evidence or combine their illustrative posteriors.
This correction improves measurement-harness ergonomics. A resulting pass can
substantiate the bounded installed workflow, not a product improvement caused by
the aliases, general usefulness, or a retroactive pass for runs 1 and 2.

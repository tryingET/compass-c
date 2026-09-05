# Conditional calculators

All calculations require explicit inputs. Do not populate probabilities, ethical
weights, causal mechanisms, or payoff numbers without labeling and justifying their
origin. The functions check arithmetic and shape, not whether assumptions describe
reality. Units must be consistent. No calculator grants execution permission.

Run `python <skill-dir>/scripts/compass.py calculate KIND --parameters 'JSON'`.
Avoid shell-dependent quoting: invoke Python with an argv list and json.dumps
when driving the CLI programmatically. Shell examples below are illustrative;
Windows and macOS execution have not been tested in this revision. The return envelope is `{"ok": true, "data": ...}`; validation failures
use `{"ok": false, "error": {"code": ..., "message": ...}}` and exit code 2.

| Kind | Required JSON fields | Limits and interpretation |
|---|---|---|
| compare | actions, scenarios, payoffs | Payoff matrix is actions × scenarios; maximize payoffs. Computes worst cases and max regret. Optional probabilities (sum 1) add expected values. It does not choose the normative criterion, evaluate hard constraints, or verify that actions are admissible. |
| committee | members, accuracy, correlation | Odd committee size 1–101; common-shock/independent mixture. Does not evaluate real experts or general ensembles. |
| bundle | test_accuracy, test_cost, gain, loss | Two independent uniform binary facts; success depends on their parity. Independent symmetric test noise, accuracy 0.5–1. It illustrates complementarity, not arbitrary research design. |
| feedback | a, gain, delay | Constant linear recurrence x[t+1]=a*x[t]−gain*x[t−delay], delay 0 or 1. Characteristic-root stability; no arbitrary delays or nonlinear plants. |
| recovery | capacity, committed, proposed, reserve | One resource; computes the reserve margin. No resource is actually reserved. |
| tail | immediate, recurring, starts_at, discount | Effect starts in period >=1. Optional horizon is inclusive; omission uses infinity and requires discount<1. Discounting and effect assumptions are user inputs, not ethical conclusions. |
| brier | probabilities, outcomes | Matching nonempty lists; binary outcomes 0/1. Scores resolved forecasts, not alignment. |

## Examples

```bash
python <skill-dir>/scripts/compass.py calculate bundle --parameters '{"test_accuracy":0.95,"test_cost":3,"gain":100,"loss":400}'
python <skill-dir>/scripts/compass.py calculate feedback --parameters '{"a":1.2,"gain":0.5,"delay":1}'
python <skill-dir>/scripts/compass.py calculate recovery --parameters '{"capacity":10,"committed":0,"proposed":8,"reserve":2}'
```

The parity pair has value 20.25 under those assumptions; the feedback model has
spectral radius sqrt(0.5); the resource example has zero remaining reserve margin.
These are conditional checks, not empirical observations.

# Prospective experimental-partner dogfood

This is author-visible development evidence. It is not a controlled host study,
an empirical probability calibration, release approval, or proof of the entire
product vision.

The retained plan was computed before the new invariant check. Its declared
hypothetical priors, likelihoods, utilities and costs favored further arithmetic
review without a test and proposed the bounded invariant check at conditional net
information value 4.2. The check then actually passed all 32 deterministic
three-state cases against independently computed exact posteriors, Bayesian
martingale consistency, and sample/perfect information value inequalities.

The retained observation was passed to `update_beliefs`. Its posterior was
`[133/148, 15/148]`, and the conditional winner changed to accepting the arithmetic
implementation for integration review. `action_permission` remained `not_granted`.
The inference depends on the declared hypothetical likelihoods; the actual
observation establishes only that these arithmetic checks passed.

`experiment-plan.json`, `experiment-observation.json`, and
`experiment-revision.json` preserve the original timestamps and numerical payloads.
During archival, the temporary observation source locator in the observation and
revision was replaced with the repository-relative path to the same retained
observation. No probabilities, results or timestamps were recomputed for archival.

`experiment-partner.py` contains the same model and invariant check, with an added
explicit output directory and exclusive file creation. To reproduce prospectively
without replacing these retained observations, choose a fresh directory:

```bash
python evals/dogfood/2026-09-08/experiment-partner.py plan --output-dir /path/to/new-run
python evals/dogfood/2026-09-08/experiment-partner.py observe --output-dir /path/to/new-run
```

Run with the installed canonical package or set `PYTHONPATH=src` from the repository.
Existing plan, observation and revision files are never overwritten. A rerun is
new development evidence and receives its own timestamps.

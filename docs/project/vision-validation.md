---
summary: "Observable acceptance boundaries for every COMPASS-C vision clause."
read_when:
  - "Checking what implements the vision and what evidence can substantiate it."
type: "reference"
---

# Vision acceptance and evidence

The durable [vision](vision.md) specifies outcomes, with no numeric release
threshold or requirement to support every vendor. This mapping makes those outcomes
inspectable without turning an aspirational horizon into an invented approval.
The [living posture](product_posture.md) binds the current assessment to committed
evidence. This file defines acceptance boundaries, not an AK task queue.

| Vision clause | Observable acceptance | Owning evidence |
|---|---|---|
| Inspect, falsify, revise and hand off | A real decision retains sources, alternatives, checks, reversal conditions and the earlier position after changed evidence | `evals/dogfood/2026-09-08/initial-brief.json`, `revision-trace.json`, `final-brief.json` |
| Modular and local-first | Guidance-only use, dependency-free installed core, portable CLI and optional MCP operate separately | `pyproject.toml`; `tests/test_distribution.py`; `tests/test_horizon_interfaces.py`; `tests/test_mcp_integration.py` |
| Provenance, uncertainty and honest authority | Every new workflow preserves supplied models or sources, distinguishes conditional arithmetic from verification, and grants no action permission | `tests/test_portfolio.py`; `tests/test_experiments.py`; `tests/test_evidence_updates.py` |
| v1 inspectable briefs | Current and stale material, uncertainty, conditions and outcomes remain visible | `tests/test_decision_lifecycle.py`; `tests/test_cli_journey.py` |
| v1 sensitivity | Exact probability-path preference crossings, ties and narrow intervals are preserved | `tests/test_sensitivity.py` |
| v1 compatible records | Frozen schema-1/2 fixtures retain their original behavior; history and experiment upgrades are explicit and transactional | `tests/test_storage_safety.py`; `tests/test_decision_lifecycle.py`; `tests/test_schema3.py` |
| v1 directly verified client paths | Actual installed package/CLI, portable process and MCP SDK canaries work on the declared artifacts | `tests/test_horizon_interfaces.py`; `.github/workflows/ci.yml`; retained final-client exercise |
| v1 measured usefulness | Actual task observations and a frozen comparative study, with noise, regressions, grading uncertainty and inference limits retained | `evals/observations/2026-09-08-work-mode-guidance/README.md`; no generalized benefit follows from this small diagnostic |
| v2 opt-in evidence updates | Preview changes nothing; explicit apply commits an entire sourced batch at one revision or rolls it all back | `tests/test_evidence_updates.py` |
| v2 invalidation, reversal and outcome review | Declared dependencies and prior recommendations become stale; source/history and review conditions survive | `tests/test_evidence_updates.py`; actual dogfood revision trace |
| v3 shared constraints and sequencing | All feasible bounded portfolios satisfy capacity, exclusions and dependency order; cycles and unknown dependencies fail | `tests/test_portfolio.py` |
| v3 option value and disagreement | Explicit deferral values and distinct stakeholder optima remain visible; no aggregate compromise is invented | `tests/test_portfolio.py`; `evals/dogfood/2026-09-08/portfolio-model.json` and `portfolio-output.json` |
| v4 decision-changing uncertainty | No-test baseline, perfect/sample information value, costs and each conditional preference branch are inspectable | `tests/test_experiments.py` |
| v4 bounded experiments and revised models | Finite one-observation proposals respect declared bounds; sourced observations update the model while retaining its prior; impossible observations fail | `tests/test_experiments.py`; prospective `evals/dogfood/2026-09-08/experiment-plan.json`, `experiment-observation.json`, `experiment-revision.json` in the same directory |
| v4 persisted experimental handoff | A fresh client resumes frozen models and protocols, previews a sourced result without writing, and applies it once with prior/posterior history and dependency invalidation | `tests/test_lifecycle.py`; `tests/test_lifecycle_interfaces.py`; `tests/test_lifecycle_capacity.py`; frozen protocol and actual assessments under `evals/dogfood/v4-lifecycle/` |
| Specialist ownership | Selected specialists retain the main task; negative, overlap and pressure cases remain in evaluation | `skills/compass/evals/cases.json`; actual host diagnostic corpus |
| First consumer is this repository | The tool is used on actual build decisions, observed failures, corrections and installed-client use | `evals/dogfood/2026-09-08/` |
| Skill and learning adoption | Deterministic requirements belong in code/tests; substantive skill optimization uses the source-owned method; KES promotion or another recipient's adoption needs actual owner evidence | `.pi/skills/compass-c-maintainer/references/improvement.md`; no automatic promotion or wider rollout |

## What the observations establish

The horizons are cumulative. The saved v4 workflow uses v1's conditional models
and v2's evidence/history contracts; it does not replace the v3 portfolio tools.
V3 sequencing currently reports dependency layers under total resource budgets.
Its option value is caller-supplied deferral value. It does not derive timed
resource schedules or real-option valuations automatically. Those stronger
algorithms are not promised by the current finite portfolio contract.

The saved-workflow exercise used fresh preparer/resumer pairs and the same isolated
0.6.0 wheel. Run 1 retained 11 lifecycle operations and failed its effort gate.
A narrow guidance correction removed redundant reads. Run 2 retained eight
successful operations plus a failed executable-path attempt, and still failed.
An explicit capture-helper alias then removed the repeated path transcription;
run 3 completed eight operations without failures. Each actual arithmetic check,
source, posterior, command, and failed assessment remains inspectable. The helper
change is measurement ergonomics, not a runtime feature or proof of product benefit.
Repeated checks of the same artifact do not become independent reliability evidence.

The retained build dogfood is real first-consumer use. In the guidance diagnostic,
four fresh sessions produced 32 actual answers. A/A scored 7/8 to 7/8; A/B scored
7/8 to 8/8 with no observed regressions. The exact paired sign-test p-value is 1.0,
and the single improvement depends on a documented grading distinction. This is
measured local behavior, not established general improvement or independent
real-world benefit. The frozen skill bytes and manually injected condition remain
explicit; native host discovery was not measured.

## External boundaries

`scripts/ci/full.sh` also checks repository governance. An empty task-scope directory
reports no snapshots to validate. The checked-in AK-5641 and AK-5673 snapshots are
compared with live AK exports and fail closed without AK. Live AK authority cannot
be reconstructed from a source checkout. The canonical company ontology is consumed
at `softwareco/ontology`. Earlier sessions could not retrieve it: its declared
GitHub backing repository returned 404. On 2026-09-26 the workspace held a checkout
backed by a local-network GitLab remote, and ROCS validation passed against it. An
unavailable owner source must still never be replaced with a stub, copied projection
or invented pass. These development gates do not become core runtime dependencies.

The vision does not require a registry release, every vendor host, a shared service,
background monitoring or fleet rollout. If pursued, those operations retain their
own owner and evidence requirements. No software test can guarantee that all future
consequential decisions improve.

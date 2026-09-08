---
summary: "COMPASS-C decision-support library, CLI, portable skill, and integration tooling."
read_when:
  - "You are evaluating, installing, integrating, or changing COMPASS-C."
type: "reference"
---

# COMPASS-C

**Charter → Observe → Model → Probe → Anticipate → Select → Self-correct**

COMPASS-C is a local-first, computational refinement of the COMPASS decision framework. It
combines a Python library, JSON CLI, revisable SQLite decision records, bounded calculators,
and a portable Agent Skill for comparing alternatives under uncertainty.

COMPASS-C is advisory. A calculation, complete record, or recommendation never grants
permission to spend, deploy, send, delete, or otherwise act outside the user's authority.

## Status

Version **0.5.0** adds coordinated portfolio comparison, bounded experiment planning,
result-conditioned model updates, and atomic evidence batches to inspectable decision
briefs, exact sensitivity, compatible records, and paired evaluation reports.
The core is **standalone and standard-library only**. Agent Kernel and other development
systems are not required to install or use it. MCP is an optional, separately installed extra.

Executable acceptance tests cover the library, fresh-process CLI, portable skill, and
local MCP SDK client/server path. The included 24-case skill corpus remains author-visible
development material. Vendor-host discovery, account installation, and improved decision
quality still require direct host evidence; local tests cannot establish those outcomes.

This repository now [dogfoods its own decisions](evals/dogfood/2026-09-08/final-brief.json)
and retains a [small actual host evaluation](evals/observations/2026-09-08-work-mode-guidance/README.md).
The study found one additional passing case with guidance and no regressions; its
sample and grading uncertainty do not establish general improvement. See the
[vision acceptance map](docs/project/vision-validation.md) for every horizon and its evidence boundary.

`LICENSE` exactly matches `tryingET/pi-extensions`, including its provider rider. It is **not
standard MIT**. Review the license before distributing or installing the skill in a restricted
host.

## Components

| Path | Purpose |
|---|---|
| `src/compass_c/` | Canonical notebook, calculations, paired evaluation, CLI and optional MCP implementation |
| `skills/compass/` | Portable skill, conditional references, generated scripts, and development cases |
| `.pi/skills/compass-c-maintainer/` | Repo-local maintenance skill candidate, KES improvement intake, and development routing cases; not shipped in portable skill archives |
| `scripts/build_skill.py` | Regenerates standalone skill scripts from the canonical package |
| `scripts/build_archives.py` | Produces deterministic toolkit, skill, and skills-only plugin archives |
| `install_skill.py` | No-overwrite install and remotely verified replacement workflow |
| `integrations/mcp_server.py` | Compatibility wrapper for the installed `compass-c-mcp` stdio adapter |

## Quick start

```bash
python -m pip install .

compass-c calculate bundle --parameters \
  '{"test_accuracy":0.95,"test_cost":3,"gain":100,"loss":400}'
```

Under that explicitly synthetic parity model, the pair value is `20.25`. This is conditional
arithmetic, not empirical validation.

Create and inspect a local decision record:

```bash
compass-c --db .compass/decisions.sqlite3 start \
  --objective "Choose between a pilot and a full launch" \
  --stakes high \
  --constraints '["No deployment without owner approval"]'

compass-c --db .compass/decisions.sqlite3 list
compass-c --db .compass/decisions.sqlite3 brief <decision-id>
```

Construction, calculations, and reads do not create storage. Only a validated `start` command
may initialize a new notebook.

Use `record` to retain sourced evidence, alternatives, checks, limitations, a
conditional decision, and explicit `reversal_condition` notes. `brief` groups the
current material, preserves its provenance, and separates stale conclusions.
`revise` appends corrected evidence with a reason and invalidates affected conclusions
without overwriting history. Existing schema-1 records stay readable; `migrate`
explicitly upgrades them before the first revision operation.

Find the point where a conditional choice changes:

```bash
compass-c calculate sensitivity --parameters \
  '{"actions":["pilot","delay"],"scenarios":["success","failure"],"payoffs":[[10,-10],[0,0]],"probability_start":[0,1],"probability_end":[1,0]}'
```

This synthetic model switches from delay to pilot at probability `1/2`, with a tie
at the boundary. Exact fraction coordinates preserve even very narrow intervals;
no probabilities or decision criteria are chosen for you.

Coordinate a set of decisions with shared constraints and competing preferences using
[`calculate portfolio`](skills/compass/references/portfolio.md). Compare bounded
information-gathering options and update a model from an explicit observed result using
[`calculate experiment` and `calculate update_beliefs`](skills/compass/references/experiments.md).
Both preserve supplied assumptions and provenance. Portfolio analysis retains disagreement;
experimental analysis uses the declared expected-value model without executing an experiment.

`update-evidence` previews a sourced replacement batch; adding `--apply` commits the
whole batch at the supplied revision. A stale revision or invalid member changes nothing.

See [the standalone workflow](docs/project/usage.md) for the complete record lifecycle
and [evaluation](docs/project/evaluation.md) for reporting paired host observations.

## Validation and packaging

```bash
uv sync --extra dev
just check
just test
just ci
just build
```

`just ci` verifies generated-file drift, lint, tests, skill structure, template policy, and
archive reproducibility. The optional MCP test suite executes when the MCP extra is installed;
CI also runs it against an isolated built wheel. These checks do not prove improved reasoning.

The repo-local maintainer skill adopts `agent-skill-engineer` with explicit handoffs,
not a copied universal workflow. `scripts/validate_skill.py` checks both packages.
Pi project-skill discovery depends on trusting/loading this checkout; committing
files does not prove discovery, actual use, or behavioral improvement. KES signals
are reviewed improvement inputs, not permission for automatic self-modification.
See the existing [vision](docs/project/vision.md) for the standalone v1-v4 horizons
and [product posture](docs/project/product_posture.md) for current proof gaps.

## Skill installation

Preview a first local installation:

```bash
uv run python install_skill.py --dry-run
```

After a public commit is verified, install that exact published skill:

```bash
commit=$(git rev-parse HEAD)
uv run python install_skill.py \
  --repository tryingET/compass-c \
  --commit "$commit"
```

Replacing an existing installation additionally requires `--replace` and a non-empty
rights-holder permission record. The prior skill is backed up outside the discovery root.
This installs local files only; it does not modify a ChatGPT account.

See [installation and publication boundaries](docs/project/installation.md).

## Optional MCP adapter

```bash
python -m pip install '.[mcp]'
python scripts/configure_mcp.py --db "$PWD/.compass/decisions.sqlite3"
```

The command prints configuration; it does not edit host settings. The installed
`compass-c-mcp` entry point uses the pinned MCP SDK 2.1.1. Local stdio round-trips
are executable acceptance tests; each vendor host still needs its own discovery
and fresh-session verification. Keep the adapter local; shared hosting is out of scope.

## Provenance

The repository was rendered from Softwareco's `tpl-project-repo` Python profile. The skill
revision applies the `tryingET/procesio-cli` `agent-skill-engineer` methodology: bounded routing,
progressive references, frozen criterion IDs, deterministic helpers, explicit failure semantics,
and honest evidence labels. The public shared conversation that supplied the design is recorded
as source provenance in `docs/project/source-provenance.md`; private reasoning traces are not
included.

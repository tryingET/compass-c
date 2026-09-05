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

Version **0.3.0** is a provisional release. Local software and packaging checks are executable.
The included 24-case skill corpus is author-visible development material, not a completed A/B
behavioral evaluation. Cross-client discovery, live MCP round-trips, and ChatGPT account
installation are not established by repository tests.

`LICENSE` exactly matches `tryingET/pi-extensions`, including its provider rider. It is **not
standard MIT**. Review the license before distributing or installing the skill in a restricted
host.

## Components

| Path | Purpose |
|---|---|
| `src/compass_c/` | Canonical notebook, calculations, and CLI implementation |
| `skills/compass/` | Portable skill, conditional references, generated scripts, and development cases |
| `scripts/build_skill.py` | Regenerates standalone skill scripts from the canonical package |
| `scripts/build_archives.py` | Produces deterministic toolkit, skill, and skills-only plugin archives |
| `install_skill.py` | No-overwrite install and remotely verified replacement workflow |
| `integrations/mcp_server.py` | Optional, provisional local stdio MCP adapter |

## Quick start

```bash
uv sync --extra dev
just test

uv run compass-c calculate bundle --parameters \
  '{"test_accuracy":0.95,"test_cost":3,"gain":100,"loss":400}'
```

Under that explicitly synthetic parity model, the pair value is `20.25`. This is conditional
arithmetic, not empirical validation.

Create and inspect a local decision record:

```bash
uv run compass-c --db .compass/decisions.sqlite3 start \
  --objective "Choose between a pilot and a full launch" \
  --stakes high \
  --constraints '["No deployment without owner approval"]'

uv run compass-c --db .compass/decisions.sqlite3 get <decision-id>
```

Construction, calculations, and reads do not create storage. Only a validated `start` command
may initialize a new notebook.

## Validation and packaging

```bash
just check
just ci
just build
```

`just ci` verifies generated-file drift, lint, tests, skill structure, template policy, and
archive reproducibility. It does not prove improved reasoning behavior or production readiness.

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
uv sync --extra mcp
uv run python scripts/configure_mcp.py --db "$PWD/.compass/decisions.sqlite3"
```

The command prints configuration; it does not edit host settings. The adapter remains
provisional until tested against the target MCP client and SDK version.

## Provenance

The repository was rendered from Softwareco's `tpl-project-repo` Python profile. The skill
revision applies the `tryingET/procesio-cli` `agent-skill-engineer` methodology: bounded routing,
progressive references, frozen criterion IDs, deterministic helpers, explicit failure semantics,
and honest evidence labels. The public shared conversation that supplied the design is recorded
as source provenance in `docs/project/source-provenance.md`; private reasoning traces are not
included.

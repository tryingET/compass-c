---
summary: "Minimal ROCS CLI for ai-society, including commands, ref resolution, and CI profile behavior."
read_when:
  - "When using or vendoring rocs-cli"
  - "When checking supported commands or CI wrapper behavior"
---

# rocs-cli

Minimal ROCS CLI for ai-society.

## Agent quick start

Do not assume `rocs` is globally installed. From this source checkout run
`uv run --frozen python -m rocs_cli ...`. In a consumer repository prefer its
checked-in `./scripts/rocs.sh ...`; a bootstrapped consumer's deterministic
acceptance entrypoint is `./scripts/ci/full.sh`.

Run the selected launcher with `contracts` (for example,
`./scripts/rocs.sh contracts`) before automating an unfamiliar operation: schema
3 declares its conditional filesystem effects, required authority artifacts, and
observable exit codes. For ontology retrieval, prefer `summary`, `pack`, `rules`,
and `explain` over reading an entire ontology source tree.

Commands:
- `rocs version`
- `rocs constitution` → `validate|challenge|differential|mutate` (proposal-only; never activates rules)
- `rocs repair-market --market bids.json` (stable Pareto frontier; never selects/applies a winner)
- `rocs context` → `create --root . --input path:ontology/src/example.md --artifact-root artifacts/intelligence --out capsule.json`
- `rocs proposal` → `validate --capsule capsule.json --proposal proposal.json`
- `rocs proposal` → `compile --capsule capsule.json --proposal proposal.json --approval approval.json --ontology-root . --artifact-root ../rocs-artifacts --out plan.json`
- `rocs transaction` → `prepare|simulate|apply|verify|rollback` (the sole ontology-mutation path)
- `rocs discover-capabilities --json` (closed, non-mutating protocol negotiation)
- `rocs discover --repo . --request-json - --tool-kind development_runtime --tool-manifest-digest sha256:... --json --no-index-cache --no-env-file` (deterministic development discovery; no prose in results)
- `rocs route-capabilities --json` (separate closed, non-mutating semantic route protocol negotiation)
- `rocs route --repo . --policy-owner-repo-id synthetic-owner --policy-owner-repo-root ../synthetic-owner --routing-policy-root ../synthetic-policy --routing-policy policy.json --routing-provenance provenance.json --request-json - --tool-kind development_runtime --tool-manifest-digest sha256:... --json --no-index-cache --no-env-file` (stdin-only development routing over explicit synthetic policy; no refs, network, cache, dotenv, or ambient owner root)
- `rocs rules [--json]`
- `rocs explain <rule_id> [--json]`
- `rocs resolve --repo . [--profile <name>] [--resolve-refs] [--json]`
- `rocs summary --repo . [--json]`
- `rocs validate --repo . [--profile <name>] [--resolve-refs] [--strict-placeholders] [--ruleset dev|strict]`
- `rocs validate --repo . [--validate-deps]` (optional: enforce strict schema on ref layers too)
- `rocs validate --repo . --only path|ref --layer <name>`
- `rocs diff --repo . --baseline <repo:...@ref> --resolve-refs [--profile <name>]`
- `rocs lint --repo . [--fail-on-warn] [--ruleset dev|strict]`
- `rocs check-inverses --repo . [--fix]`
- `rocs graph --repo . [--relation is_a] [--format excalidraw|excalidraw-cli-json|dot] [--json] [--out <path>]`
- `rocs cache dir|ls|prune|clear`
- `rocs normalize --repo . [--apply]`
- `rocs pack <ont_id> --repo . [--profile <name>] [--resolve-refs] [--json]` (`<ont_id>` may be a concept or relation id; fails closed if limits exclude the requested root doc)
- Bound automatic follow-up adds `--profile <name> --expected-snapshot-digest sha256:... --expected-document-digest sha256:... --json --no-index-cache --no-env-file`; both preconditions are mandatory and mismatches fail closed.
- `rocs build --repo . [--profile <name>] [--resolve-refs] [--clean] [--json]` (fail-closed: refuses invalid ontology content and clears stale build artifacts before each run)

Scope (MVP):
- Validate ROCS repo structure + ontology front matter schema.
- Support both managed ontology layouts:
  - standard repo layout: `ontology/manifest.yaml`, `ontology/src/`, `ontology/dist/`
  - ontology-repo root layout: `manifest.yaml`, `src/`, `dist/`
- Build local artifacts into the managed `dist/` directory for the selected layout.
- Emit `authority-receipt.json` plus per-command `authority-receipt.<command>.json` artifacts inside that managed `dist/` directory for `build`/`validate` runs so local consumers can see authority mode and per-layer resolution sources without losing multi-step evidence.
- Resolve layered ontology refs from a local workspace only.

Ontology source contract (opt-in):
- A layer opts in only through `rocs.source_contract: ontology-markdown-v1` in the `manifest.yaml` adjacent to that layer's `src/` root. Layers without the selector retain legacy behavior; mixed views dispatch each layer separately before cross-layer identity/reference checks.
- V1 admits the closed 1 MiB, strict-UTF-8, exact-delimiter frontmatter profile and exact concept/relation paths and fields documented in [`docs/project/ontology-markdown-v1.md`](docs/project/ontology-markdown-v1.md). YAML duplicates, aliases, merges, tags, non-string keys, unknown fields, malformed lifecycle/reference data, unsafe membership, and placeholders fail closed.
- Every interpreting source operation uses the shared dispatcher: validate/build/summary/lint/diff/graph/inverse checks/normalize, both pack modes, discover/route, and transaction source reads. `rules` and the current `explain` implementation do not open source documents.
- A `rocs-source-contract-conformance.v1` claim is source-contract/schema/reference-only, binds the exact admitted corpus digest and operation, and is emitted only after complete success. Rejected, partial, or resource-exhausted operations emit no such claim. It is not a semantic-correctness, publication, adoption, activation, or currentness verdict.
- `context create` is deliberately raw UTF-8 custody: its capsule contains no source-conformance claim. Any transaction or other later interpreter re-admits selected bytes through the layer contract.

Layer refs (optional):
- Supported locator form: `<repo:<workspace-relative-project-path>@<ref>>`
  - example: `<repo:core/ontology-kernel@main>`
  - example: `<repo:softwareco/ontology@main>`
- Legacy `<gitlab:...>` locators are no longer supported.
- `--resolve-refs` enables resolving ref layers from the local workspace.
- Resolution source:
  1) workspace clone (offline)
- Workspace config:
  - `--workspace-root <path>` (or `ROCS_WORKSPACE_ROOT`): workspace root containing local clones (recommended: `~/ai-society`).
  - `--workspace-ref-mode strict|loose` (or `ROCS_WORKSPACE_REF_MODE`):
    - `strict` (default): use workspace only if `HEAD` matches the requested ref
    - `loose`: use workspace checkout even if it doesn’t match the requested ref
  - `repo:` locators bind by workspace layout, not remote origin URL.
- Diagnostics:
  - `--show-resolve-sources` adds `(source=workspace|path)` to `rocs resolve` / `rocs summary` text output.
  - `--show-resolve-details` adds workspace skip reasons in text output and includes per-layer `details` in JSON output.
- Selector contract:
  - Explicit selectors fail closed. If `--layer` names no declared layer, or `--only`/`--layer` together match nothing, commands return a non-zero error instead of silently operating on zero layers.
  - Each `rocs.layers[]` entry must declare exactly one of `path` or `ref`; mixed entries are rejected instead of silently preferring one.
- Dotenv loading (so you don’t need to `export` vars):
  - Highest priority: pass `--env-file <path>`.
  - Otherwise `rocs` auto-loads the first existing file from:
    - `ROCS_ENV_FILE`
    - `<repo>/.env` (where `<repo>` is `--repo`)
    - `holdingco/governance-kernel/.env` (when running inside the ai-society workspace)
- Cache location: `ROCS_CACHE_DIR` or `$XDG_CACHE_HOME/rocs` or `~/.cache/rocs`.
- Incremental doc/index cache (local-only): enabled by default; disable with `rocs --no-index-cache ...` or `ROCS_INDEX_CACHE=0`. Debug with `rocs --index-cache-debug ...` or `ROCS_INDEX_CACHE_DEBUG=1`.

Examples:
- `rocs resolve --repo . --resolve-refs --workspace-root ~/ai-society --workspace-ref-mode strict --show-resolve-sources`
- `rocs summary --repo . --resolve-refs --workspace-root ~/ai-society --json`
- `rocs diff --repo . --baseline <repo:core/ontology-kernel@main> --resolve-refs --workspace-root ~/ai-society`

AI Society convention (recommended):
- Set `ROCS_WORKSPACE_ROOT=~/ai-society`.
- Use `<repo:core/ontology-kernel@main>` and `<repo:softwareco/ontology@main>` in manifests for layered repos.
- Wire `scripts/ci/full.sh` into your preferred local gate runner (for example a Pi task or a git hook) instead of relying on remote ref fetches.

Graph export:
- `rocs graph` writes an `.excalidraw.json` file by default (open it in Excalidraw).
- For `excalidraw-cli` (external): use `--format excalidraw-cli-json`, then run `excalidraw-cli create <file> -o graph.excalidraw`.

Tests:
- `uv run --frozen python -m unittest discover -s tests -p 'test_*.py' -q`

CI profile wrapper (template-side policy contract):
- Script: `scripts/ci/full.sh`
- Layout note: ontology repos may live either at `ontology/` inside a normal repo or directly at repo root when the repo itself is the ontology container.
- Profiles via `ROCS_CI_PROFILE=local-dev|branch-ci|main-strict`
  - `local-dev`: offline-first default; runs `--only path` unless `ROCS_LOCAL_RESOLVE_REFS=1`, and that opt-in path enables `--resolve-refs` with workspace matching defaulting to `strict`
  - `branch-ci`: requires `--resolve-refs` and defaults workspace matching to `strict` (fail-closed)
  - `main-strict`: requires `--resolve-refs` and defaults workspace matching to `strict` (authoritative fail-closed gate)
- `ROCS_WORKSPACE_REF_MODE` remains an explicit override when a caller intentionally needs different behavior.
- This same wrapper is the recommended local hook/Pi entrypoint for pre-push or pre-merge checks.
- Bootstrapped consumers run the checked-in `tools/rocs-cli` bundle with isolated system `python3 -I -S -B`; the generated wrapper verifies an embedded digest of `VENDORED_HASHES.json` and then every bundled file before import. It does not require `uv`, a source checkout, network access, or ambient `PYTHONPATH`. Explicit `rocs vendor TARGET` is source-project based; schema-3 generation requires a provenance-bearing Git SHA-1 checkout (or an already verified schema-3 bundle for re-vendoring). Installed legacy wheels without commit provenance retain the verified schema-2 bootstrap fallback rather than inventing a Git identity.
- Bootstrap serializes publication with a persistent external sibling lock named `.<repo>.rocs-bootstrap.lock`; it preflights and reports that coordination path separately, never exchanges or unlinks its inode, and creates no undeclared lock inside the consumer tree.
- `ontology_repo` consumers use root `manifest.yaml` and `src/`; required/optional consumers retain the nested `ontology/` layout. Generated hooks resolve the repository from their installed path, matching Git's real hook invocation contract.
- See `docs/ref-resolution-ci-strategy.md` for the architecture/policy rationale and migration guidance.
- Optional overrides:
  - `ROCS_CMD` (default: `uv run --frozen python -m rocs_cli`)
  - `ROCS_REPO` (default: `.`)
  - `ROCS_PROFILE` (optional manifest profile)

Constitutional foundry (proposal-only, offline):
- Schema-1 candidate packets bind owner/adoption scope, rationale, an allowlisted closed predicate AST, positive/negative fixtures, adversarial counterexamples, severity and suppression policy, false-positive challenges, evidence digests, and a canonical candidate digest.
- `constitution validate|challenge|differential|mutate` deterministically validates/challenges candidates, compares behavior, and generates mutants only from accepted digest-bound capability/operation contracts. It has no eval, import, shell, network, callback, generated-code, activation, suppression, or certification path.
- `repair-market` validates competing proposal-only plans and returns a stable Pareto frontier over mutation radius, owner crossings, rollback cost, convergence evidence, verification cost, and maintenance burden. It returns no winner and applies nothing.
- Rule adoption/activation is outside this repository/runtime and requires a separate owner decision and an ordinary reviewed deterministic Python implementation. See `docs/project/wave4-constitution-coverage.md`.

Intelligence membrane (optional, offline by default):
- `context create` emits a canonical, content-addressed schema-1 raw-custody capsule from explicitly named UTF-8 files. Inputs are tagged `path` or `ref`; symlinks, traversal, duplicate paths, and files outside `--root` fail closed. Capture neither parses ontology Markdown nor emits source-contract/semantic conformance; interpreting transaction paths re-admit opted-in bytes.
- A model/adapter may only consume capsule bytes and return proposal bytes. The importable `ProposalAdapter` protocol grants no shell, filesystem, network, validation, or approval authority, and ROCS invokes no adapter or network by default.
- `proposal validate` treats strict JSON proposals as untrusted data. Unknown fields/capabilities, digest drift, undeclared paths, and ref-layer writes fail closed.
- `proposal compile` additionally requires a separate schema-1 operator approval bound to the proposal digest. It emits a deterministic schema-1 plan and never applies operations. `--out` is a relative path bounded by an existing `--artifact-root`, which must be disjoint from `--ontology-root`; absolute paths, traversal, symlinks, command-input collisions, and capsule path/ref-layer collisions fail closed. Plans bind tool/registry versions, capsule/proposal/approval digests, closed capabilities, exact paths, human authority, verifier, rollback, and proposed operations.
- `transaction prepare` binds that immutable plan and capsule to base authority, exact byte preimages, semantic ID/blast-radius/obligation effects, owner partitions, deterministic gates, and rollback. `simulate` is non-mutating. `apply` alone mutates and requires a distinct `operator:` approval bound to the transaction digest; it revalidates all inputs, rejects drift/ref/cross-owner writes, stages on the target filesystem, runs ROCS gates, and compensates every failed publication byte-exactly. `verify` and `rollback` consume digest-validated content-addressed receipts and reject post-apply drift. Rollback is itself a generation-atomic mutation authorized by the supplied transaction and receipt; it restores receipt-bound bytes and exact modes, requires the live generation still match the postimage, and does not obtain a new operator approval. These operations execute no shell, model, or network code.

Wave 1 convergence CLI (the former script API was removed with no shims):
- `rocs bootstrap TARGET --class required|optional|ontology_repo [--dry-run]` installs the complete class contract.
- `rocs converge TARGET --class required|optional|ontology_repo [--dry-run]` idempotently restores that contract and removes replaced generated scripts.
- `rocs vendor TARGET [--release-version X.Y.Z] [--dry-run]` publishes `pyproject.toml`, `README.md`, the complete package, and one schema-3 `VENDORED_HASHES.json` materialization receipt. The receipt binds the current 40-hex Git SHA-1 commit, exact bundled `uv.lock`, every regular bundle file, and a SHA-256-over-JCS manifest digest.
- `rocs fleet` provides distinct `observe`, `plan`, `apply`, and `run` operations. Each takes a workspace root and policy; apply supports dry-run and run supports audit-only, patch, or apply mode.
- `rocs release plan|apply --version X.Y.Z`, `rocs verify PATH`, `rocs cleanup`, and `rocs doctor` provide release, integrity, maintenance, and standalone acceptance operations.
- Scheduling assets retained under `scripts/{cron,systemd}` invoke `rocs fleet run`; they contain no operational behavior.

YAML tooling (optional, for shell-level policy inspection):
- Runtime YAML parsing in `rocs-cli` is already provided by `pyyaml`.
- Install CLI helpers via extras: `uv sync --extra tooling`
- Run query helper: `uv run --frozen --extra tooling yq --version`

Perf harness (synthetic, offline):
- `rocs benchmark --command build --count 600 --runs 7`
  - The benchmark and deterministic repository generator are importable package capabilities.

Exit codes:
- `0`: success
- `1`: error (invalid config/usage; schema/validation errors; malformed ontology content; internal errors)
- `2`: action required / partial success (e.g. `rocs normalize` changes needed; `rocs diff` breaking removals detected; `rocs pack` unknown ont_id)

JSON output:
- Prefer `--json` for machine output.
- When JSON output is selected, errors are emitted as `{"ok": false, "error": {...}}` and the process exits non-zero.

Lint (ruff):
- Tool pins: `scripts/tool_versions.json`
- Run: `uvx ruff==$(python -c 'import json; print(json.load(open(\"scripts/tool_versions.json\"))[\"ruff\"])') check .`

Type checking:
- Prefer `ty` (Astral). See `docs/ty.md`.

VHS recordings (documentation by recorded behavior):
- Install `vhs` (and its deps: `ttyd`, `ffmpeg`), then run: `core/rocs-cli/scripts/vhs-run.sh`
- Outputs land in `core/rocs-cli/artifacts/vhs/` (gitignored); share the `.gif` when reporting behavior regressions.

## Wave 1 operational CLI

Wave 1 removes the executable-script API. The closed operations are discoverable
with `rocs contracts`: `fleet observe|plan|apply|run`, `bootstrap`, `converge`,
`vendor`, `release plan|apply`, `verify`, `cleanup`, `doctor`, `benchmark`, and
`generate`. Core behavior is importable from `rocs_cli.fleet`,
`rocs_cli.wave1`, and `rocs_cli.generator`.

The emitted command contract is schema 3: the former `mutates` boolean was
removed without a compatibility shim and replaced by closed conditional
filesystem-effect and required-authority-artifact rules. See
[`docs/project/wave7-effects-contract-coverage.md`](docs/project/wave7-effects-contract-coverage.md).

A consumer is pinned by `VENDORED_HASHES.json` schema 3. `rocs vendor TARGET`
publishes one exact package materialization; `rocs verify TARGET` checks the
Git-SHA-1-shaped source commit, bundled lock digest, complete path/hash set, and
RFC 8785/JCS receipt digest. This proves exact local bundle identity and
provenance only—not canonical cross-builder bytes, package publication, semantic
correctness, or consumer adoption/currentness. Verification does not depend on a
sibling checkout or workspace PATH.

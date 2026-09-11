---
summary: "Boundaries and verified sequence for publication, local skill installation, and host integration."
read_when:
  - "You publish COMPASS-C, install or replace the skill, or configure MCP/ChatGPT."
type: "procedure"
---

# Publication and installation are separate states

## Standalone package

Install the toolkit from a checkout with `python -m pip install .`, or install a
verified built wheel. The core library and CLI use only Python's standard library.
Agent Kernel, ROCS, Pi and other development coordination tools are not runtime
requirements. A portable skill installation also works independently of those systems.

MCP is opt-in: `python -m pip install '.[mcp]'` adds the pinned SDK. Keep the
virtual environment's own interpreter path in client configuration; resolving its
symlink to the base Python loses the environment's installed packages.

## Publication sequence

Archives include declared source only: tracked Git-index paths in a checkout,
or the existing `MANIFEST_SHA256.txt` path list in an extracted toolkit. Stage
intended new source files before building an archive. Workspace notes, caches,
keys, notebook state, receipts and symlinks are excluded. The manifest is a build
allowlist and checksum inventory, not a signature or proof of publication.

Use this sequence:

1. render the Softwareco project template;
2. add and locally verify COMPASS-C;
3. commit and publish the public repository;
4. read back the public default-branch commit;
5. install that exact skill locally;
6. verify the installed standalone helper;
7. perform a fresh-host trigger, abstention, and resource-loading test.

No earlier state proves a later state succeeded.

## License gate

`LICENSE` reproduces the requested `tryingET/pi-extensions` license, including its provider
rider. It is not standard MIT. The repository and installer do not invent an exception or issue
a legal conclusion. A managed replacement requires an operator-supplied, non-empty permission
record and stores only its SHA-256 digest in the local receipt.

## Public repository readback

After publication:

```bash
commit=$(git rev-parse HEAD)
gh repo view tryingET/compass-c --json nameWithOwner,visibility,defaultBranchRef
uv run python install_skill.py \
  --repository tryingET/compass-c \
  --commit "$commit" \
  --dry-run
```

The installer verifies that the named repository is public, that the commit is the current
default-branch head, and that each published `skills/compass/` blob matches the local source.

## First local install

A first installation refuses an existing destination:

```bash
uv run python install_skill.py \
  --repository tryingET/compass-c \
  --commit "$commit"
```

The default root is `~/.agents/skills`. Use `--root` for a client's documented skill directory.
The installer stages and executes the standalone calculator before moving the skill into place.

## Managed replacement

```bash
uv run python install_skill.py \
  --replace \
  --repository tryingET/compass-c \
  --commit "$commit" \
  --permission-file /path/to/rights-holder-permission.txt
```

The old skill moves to a unique `compass-backups/` directory outside skill discovery. A
cooperating-process lock prevents concurrent replacement. On a detected installation failure,
the installer restores the prior version where safe and preserves the failed copy for review.

## ChatGPT account installation

A GitHub push and local filesystem installation do not install a ChatGPT account skill. Account
installation requires the target host's current upload/registration UI or API, applicable
permissions, license clearance, and direct post-install verification. This repository emits a
skills-only plugin archive, but archive creation is not account installation.

OpenAI's current [skills](https://learn.chatgpt.com/docs/build-skills) and
[plugins](https://learn.chatgpt.com/docs/build-plugins) guides distinguish local
skills from installable plugins. ChatGPT explicit invocation uses `@`; Codex uses
`$` or `/skills`. The guides recognize the `.codex-plugin/plugin.json` compatibility
manifest used here. Confirm the actual account/app surface before prescribing an
installation click path. No account upload or fresh ChatGPT conversation was verified
by the 2026-09-11 local work.

## MCP

`compass-c-mcp` and `python -m compass_c.mcp_server` run the optional local stdio
adapter from the installed package. `integrations/mcp_server.py` is a compatibility
wrapper. `scripts/configure_mcp.py` prints a machine-specific configuration; it
does not modify a host or require a persistent checkout path at runtime.

`tests/test_mcp_integration.py` uses the actual pinned SDK 2.1.1 client and server:
initialize, discover seventeen tools, calculate, preview and apply evidence batches,
save and resume experiments, incorporate observations once, reconnect, revise, inspect and
fail cleanly. CI repeats these scenarios against an isolated built wheel. This
establishes the local SDK path; vendor-host installation and discovery still need
a fresh-session canary against that actual client. The adapter is not a shared,
authenticated or multi-tenant service.

`STORAGE_NOT_FOUND` now explicitly describes only the configured notebook. It does
not establish whether an earlier write committed elsewhere or before state changed,
and it grants no retry permission. The existing error code/message envelope remains
compatible. Recover the original notebook and operation identity before retrying.
This clarification is not a host approval gate and cannot guarantee model compliance.

## Bounded local dogfood, 2026-09-11

- `just dogfood-hosts` (set `PI_CODING_AGENT_PACKAGE` to the reviewed installed Pi
  package directory): opt-in Linux tests, disposable homes, network-disabled host
  processes. Pi 0.84.4 global/trusted-project discovery, resource reads and withdrawal;
  Codex 0.128.0 local discovery and withdrawal. No model or permanent host changes.
- `just test-mcp`: actual configuration-driven SDK stdio checks. The separate
  incoming integration/interface suite also passed 43 scenarios against an isolated
  v0.6.0 wheel; this is distinct from account integration.
- Public-head-verified installation of skill commit
  `92f80c6b20e8cb82e144db96662e45873fac7add` succeeded. A disposable 0.3.0 to 0.6.0
  managed replacement retained a runnable backup and the operator-permission digest.
- An actual fresh GLM-5.3-flash/Pi session used six core operations through the
  seventeen-tool MCP catalog and returned the observed calculation, record ID and
  revision. This was a custom Pi SDK integration, not default installed Pi support.

See the [retained study and limitations](../../evals/observations/2026-09-11-glm-native/README.md).
The operator supplied limited provider permission under AK 9075; this does not
change `LICENSE`, authenticate other users' permission, or verify provider training
settings. Behavioral improvement, safe unattended recovery and actual personal
OpenAI account installation remain separate, unresolved claims under AK 5641.

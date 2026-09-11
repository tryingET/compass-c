---
summary: "Boundaries and verified sequence for publication, local skill installation, and host integration."
read_when:
  - "You publish COMPASS-C, install or replace the skill, or configure MCP/ChatGPT."
type: "procedure"
---

# Publication and installation are separate states

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

A non-dry-run installation with `--repository` and `--commit` verifies that the repository is
public, the commit is the current default-branch head, and every published `skills/compass/`
blob matches the local source. `--dry-run` previews the destination and local preconditions;
it returns before remote verification and must not be cited as public-head proof.

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

## MCP

`integrations/mcp_server.py` uses SDK v2's `MCPServer`. `scripts/configure_mcp.py` prints a
machine-specific local configuration without modifying a host. Its Python path preserves venv
symlinks: resolving them to the base interpreter loses the installed package and SDK.

```bash
just test-mcp
```

This explicitly installs the lockfile-selected MCP extra and launches the printed configuration
through a real Python SDK stdio client. Eight cases exercise all six tools, read/calculation
non-creation, invalid input, stale-write rejection, dependent-note invalidation, persisted
readback after server restart, and rejection of boolean/string/float revision coercion on both
write endpoints. Verified on Linux with Python 3.13.12, MCP 2.1.1 and Pydantic 2.13.5.
The dedicated check runs in CI; ordinary tests can skip MCP when its extra is absent.

This proves the local SDK transport profile, not an agent choosing MCP tools, account settings,
other SDK versions, or shared-service authentication/tenant isolation.

## Model-free host dogfooding

```bash
# Review the installed Pi SDK; substitute its actual package directory.
PI_CODING_AGENT_PACKAGE=/absolute/path/to/node_modules/@earendil-works/pi-coding-agent \
  just dogfood-hosts
```

Requires Linux user/network namespaces (`unshare`), Node, Git, Pi and Codex. The opt-in suite
uses disposable HOME/config directories under `TMPDIR` and disables network access for host
processes. It invokes no model and reads no normal host credentials. No existing installation
is replaced. If namespaces or a required client are unavailable, the opted-in check fails;
there is no fallback to an unrestricted host process.

Observed on 2026-09-11 (AK task 5641, evidence 9026):

| Path | Observed proof | Not proved |
|---|---|---|
| Local installer CLI | Exact skill file hashes, receipt, isolated standalone calculator; no-overwrite guard retained | Published-head verification, managed replacement permission, permanent install |
| Pi 0.84.4 | Fresh `DefaultResourceLoader` processes discover global and trusted-project `.agents/skills/compass`; untrusted project excluded; actual host read tool loads skill and calculator reference; withdrawal removes discovery | Model-triggered loading, abstention, decisions, repo-maintainer skill behavior |
| Codex CLI 0.128.0 | Local app-server `skills/list` reports the installed project skill enabled; fresh process no longer discovers it after withdrawal | Model turn, automatic selection, resource use, MCP host connection |
| Python MCP SDK 2.1.1 | Live stdio client/server lifecycle and safety checks above | ChatGPT or other agent-host installation |

The host suite has three opt-in cases, skipped by default CI and run explicitly for this receipt.
A test-controlled resource read is not model selection. No new model provider permission was
supplied; restricted-provider evaluation and ChatGPT upload were not attempted. Controlled
behavioral A/A and paired A/B comparisons require an approved model, cost limit, frozen criteria,
independent scoring and variance/regression reporting. Account installation additionally needs
target UI/API access and post-install readback. These remain open under AK 5641.

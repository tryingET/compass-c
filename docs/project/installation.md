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

## MCP

`integrations/mcp_server.py` is optional and provisional. `scripts/configure_mcp.py` prints a
machine-specific local configuration; it does not modify a host. Do not claim MCP connectivity
until the target client completes a live round-trip against the selected SDK version.

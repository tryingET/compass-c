---
summary: "AK 5641 local host/MCP dogfood: reproduced integration defects, bounded proof, and provider/account blockers."
read_when:
  - "You continue COMPASS-C live-host validation or investigate the MCP and archive fixes."
type: "reference"
---

# Local dogfood — AK 5641

## Authority and limits

The operator requested completion of unproven paths through dogfooding, staying on `main`.
The authorization form then expressly selected local/non-restricted paths only, without a
copyright-holder exception for restricted providers or a model spend limit. Pi, Codex, local
Python MCP and ChatGPT were selected as targets; target selection does not override that limit.
No provider trial, ChatGPT upload, existing-install replacement, public push, or release occurred.

## Observed failures and causal repairs

1. Launching the actual printed MCP configuration initially failed with
   `ModuleNotFoundError: compass_c`. `Path.resolve()` dereferenced the venv Python symlink to
   the base interpreter. Preserve the absolute venv path instead; test default and explicit
   symlink paths without installing any host configuration.
2. After fixing the interpreter, the declared MCP 2.1.1 dependency rejected `FastMCP` imports.
   Its installed migration message and metadata identify `MCPServer` as the v2 API. Adopt that
   API instead of misreporting the installed extra as absent.
3. Once connected, the stdio adapter accepted `true`, `"1"`, and `1.0` as integer revisions.
   SDK/Pydantic coercion bypassed the library's strict revision contract. Use `StrictInt` on
   record and invalidate; compare complete record readbacks before and after rejected requests.
4. A real toolkit ZIP and source tarball included `.ontology` runtime cache/session artifacts
   and SQLite WAL/SHM files. They were local only, never distributed. Exclude known runtime
   caches and SQLite sidecars in both builders; twelve synthetic exclusion tests first failed,
   then passed. Build a real sdist from a synthetic dirty checkout, without relying on Git
   ignore rules. Rebuilt local artifacts were inspected to confirm the observed leak was gone.

## Executed proof

- `just test-mcp`: eight passing cases with Python 3.13.12, MCP 2.1.1, Pydantic 2.13.5.
  Real configuration -> stdio subprocess -> SDK initialization/list -> all six tools -> restart
  readback; no model, remote transport, or simulated server. Input errors leave storage unchanged.
- `PI_CODING_AGENT_PACKAGE=<reviewed installed package> just dogfood-hosts`: three passing cases.
  Pi 0.84.4 loads global/trusted-project skills, excludes an untrusted project skill, and uses
  its real read tool for the skill and reference. Codex 0.128.0 lists the installed project
  skill enabled via local app-server. Fresh-process withdrawal checks pass in both clients.
  HOME/configs are disposable, no normal credentials are inherited, network namespaces block
  external access, and no model turn is sent. Host trust in the Pi SDK is supplied explicitly
  by the test, not inferred as a user trust decision in the normal installation.
- Local installer CLI receipts and complete skill hashes match; the installed standalone helper
  executes the bundle model and returns 20.25. This is conditional arithmetic, not efficacy.
- Archive safety plus actual sdist fixture: sixteen passing tests. `just build` succeeds;
  standalone skill/plugin hashes are unchanged by these integration-only repairs.
- Combined suite with both MCP and host opt-ins: **123 passed, 17 subtests passed**, no skips.
- `just check` and `git diff --check` pass. Initial `just ci` correctly stopped on uncommitted
  posture evidence; the repo requires an evidence commit followed by one posture-binding commit.
  Final committed-state CI evidence belongs in AK, not an inferred pass from these proxies.

Bounded live evidence was recorded as AK 9026; final validation evidence is attached to task 5641.
SCI navigation created untracked `.ontology` runtime state; it is not source or a deliverable.
It was left intact rather than deleting a possibly live tool-owned database.

## Retained proof gaps

- Automatic trigger/abstention, model-initiated reference/helper use, and improved decision
  quality remain unmeasured. A loader/read probe is not a behavioral trial.
- No fresh-host behavioral test of the repo-maintainer skill, recipient adoption, or KES runtime.
- MCP SDK connectivity does not prove an agent-host MCP connection or shared-service readiness.
- ChatGPT account installation remains permission- and account-access-gated.
- Remote publication verification and managed replacement were not exercised in this local run.

AK 5641 retains the unfinished operator request. Resume with an approved non-restricted model
and budget (or explicit applicable copyright-holder permission), plus target account/UI access
for account installation. Freeze prompts/criteria before trials; preserve failures and report
A/A variance and paired A/B regressions instead of claiming that a passing canary proves better
reasoning. These notes are candidate lessons, not promoted KES knowledge or reusable authority.

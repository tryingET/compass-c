---
summary: "Accepted decision (E*): reversibly pause discretionary COMPASS-C expansion while keeping v0.6.0 usable and persistence opt-in."
read_when:
  - "Before starting new COMPASS-C features, evaluations, integrations or skill rewrites."
  - "When checking whether a reversal condition has been met."
type: "decision"
status: "accepted"
decided: "2026-09-26"
decided_by: "@tryingET (owner)"
---

# ADR: Pause discretionary expansion (E*)

## Context

The v1–v4 horizons have bounded, tested mechanics. The outcome the vision cares about, measured usefulness, is not established:

- **8-case guidance diagnostic:** 7/8 → 8/8, p = 1.0.
- **96-trial Pi/GLM study:** its grades were found invalid (AK 9198). A jury re-adjudication did not recover the apparent gains (AK 9361), and the adjudication has its own semantic failure (AK 9362).

The 2026-09-26 rethink froze its [frame](2026-09-26-rethink-frame.md) before probing, and its [probe report](2026-09-26-rethink-probe-report.md) includes an independent critique and a measured guard. The retained evidence is in [`evals/rethink-2026-09-26/`](../../evals/rethink-2026-09-26/README.md). It found:

- **Natural use:** five model-initiated skill reads, with no downstream tool or notebook use, and zero natural notebooks.
- **Where the reasoning lives:** the owner's own COMPASS-style reasoning is kept in AK evidence, not in notebooks.
- **The guard, once built:** a mechanical claim-freshness guard recalls 43–50% of real drift at 25% precision. The hypothetical "enforce at chokepoints" option is therefore inconclusive.
- **The critic's recommendation:** an independent reviewer (Pi, `openai-codex-2/gpt-6-astra`) recommended this reversible pause, with medium confidence.

## Decision

Pause **discretionary expansion** of COMPASS-C. The pause is reversible.

- **v0.6.0 stays the supported product.** The library, CLI, portable skill and optional MCP adapter remain installable and usable.
- **Persistence stays opt-in.** Nothing is archived, withdrawn or uninstalled.

**Paused**
- New features, calculators, MCP tools, schema changes or horizons beyond v4.
- New behavioral studies, provider trials, jury cycles or evaluation infrastructure.
- The claim-freshness guard. Its prototype is archived as text in [`evals/rethink-2026-09-26/guard/`](../../evals/rethink-2026-09-26/guard/check-claim-freshness.py.txt) and is not a repository gate.
- Skill description or routing rewrites. Improving routing precision is an untested hypothesis.
- Pursuing further host or account installations.

**Continues, as maintenance**
- Fixes for correctness or security defects in shipped behavior.
- Compatibility with the supported Python versions and the pinned MCP SDK.
- Accuracy of existing documentation and evidence, including stale-claim repair.
- The repository's required gates. `product_posture.md` must be revalidated at least every 30 days, or `fast.sh` fails. This is the pause's known standing cost.
- Existing storage constraints. Do not change experiment calculation output without a stored-plan migration: stored plans are verified by recomputing them.

**Opportunistic observation only.** Record natural COMPASS use, or a naturally occurring consequential evidence change, when one happens. There is no active measurement program.

## Reversal conditions

These are from the independent critique:

- **Reconsider A (continued notebook-centric development)** if owner-chosen, consequential decisions repeatedly use cold resume or revision, and their benefits exceed the full capture and review costs compared with the existing AK workflow.
- **Reconsider C (a chokepoint guard)** if a prospective, independently observed episode shows the guard producing timely, useful corrections beyond the existing gates. The dependencies must be declared beforehand, and the owner must accept the false-alert and maintenance costs.
- **Reconsider B (a narrowed kernel)** if external consumers repeatedly use or request the calculations or invalidation semantics without the broader workflow.
- **Reconsider D (a calibration ledger)** only if real owner forecasts gain frequent, verifiable resolutions and sustained review demand.

## Consequences

- AK 5641 (host dogfood and behavior measurement) and AK 5673 (jury program) were deferred, not closed.
  *Update, later on 2026-09-26:* at the owner's instruction, AK 5673 was completed on its committed validation (AK 9370), keeping failures 9267 and 9362 and its advisory claim boundary. AK 5641 remains deferred.
- Publishing the unpublished local commits, releasing, and archiving remain separate owner decisions.
  *Update, later on 2026-09-26:* at the owner's instruction, the commits were published at `0526f34`. Releasing and archiving remain separate decisions.
- The installed skill copies predated the 2026-09-26 reference correction in `decision-checks.md`.
  *Update, later on 2026-09-26:* at the owner's instruction, they were refreshed by managed replacement with the published skill at `0526f34` (AK 10672), with the old copies kept as backups. Refreshing existing installs is maintenance, not a new installation.
  *Update, evening of 2026-09-26:* after the maintenance pass (AK 6007), the owner approved a second refresh, from the published head `0770f4e` (AK 10737).

---
summary: "COMPASS-C component model and authority boundaries."
read_when:
  - "When onboarding, changing architecture, or reviewing scope"
---

# Project model

## Core loop

`Charter → Observe → Model → Probe → Anticipate → Select → Self-correct`

The loop is event-driven, not a mandatory stage transcript. Small decisions may be brief.
Material uncertainty may cycle among observation, modeling, probing, and anticipation before a
conditional choice.

## Components

| Component | Owns | Does not own |
|---|---|---|
| Skill | Routing, reasoning workflow, boundaries, completion contract | Domain implementation or host permission |
| Python library | Validation, calculations, record state transitions | Evidence truth or policy values |
| SQLite notebook | Local record persistence and invalidation history | Protected audit logging or shared tenancy |
| CLI | Stable JSON envelopes over the library | Shell authorization or network activity |
| Installer/build tools | Reproducible artifacts and bounded local placement | ChatGPT account state or legal clearance |
| MCP adapter | Optional transport to the same library | Authentication, multi-tenant deployment, or proof of connection |

## Invariant

Capability may expand what the system can understand. Only legitimate authority, with adequate
evidence, may expand what it can do.

Belief updates may change forecasts. They do not silently change values or permissions.

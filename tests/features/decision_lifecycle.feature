Feature: Inspect and revise consequential decisions without acquiring authority
  COMPASS-C preserves source statements, uncertainty, and old reasoning so a person
  can resume, challenge, and revise a local decision record.

  Scenario: Inspect an evidence-faithful decision brief
    Given a decision has constraints, competing alternatives, evidence, and a recommendation
    And uncertainty, checks, effects, reversal conditions, and outcomes are recorded
    When I request its brief
    Then the exact current notes and provenance appear in their named sections
    And stale notes appear separately
    And completeness is structural, sources remain unverified, and action permission is not granted
    And neither the record revision nor the database bytes change

  Scenario: Revise evidence while retaining a complete history
    Given a decision contains evidence, dependent reasoning, and an unlinked recommendation
    When I explicitly replace the evidence with a reason and current revision
    Then the old evidence content and provenance remain unchanged
    And a new current note is linked to the old note in revision history
    And the old evidence, dependent reasoning, and recommendations become stale atomically
    And the decision revision advances exactly once

  Scenario: Reject unsafe replacement without partial updates
    Given an existing decision record
    When a replacement uses stale or newly invalidated dependencies, a wrong revision, or bad input
    Then a stable error explains the rejection
    And no replacement, invalidation, or revision increment is persisted

  Scenario: Open a previous schema without an implicit upgrade
    Given a notebook written in schema version 1
    When I read, list, or brief its decisions
    Then its original bytes remain unchanged
    And revision requests explain that an explicit migration is required
    When I explicitly migrate the notebook
    Then its notes, provenance, and invalidations survive unchanged
    And repeated migration is an idempotent no-op

  Scenario: Refuse unsupported or damaged storage
    Given a newer, unrelated, or malformed notebook
    When I read or request migration
    Then COMPASS-C refuses with a stable error
    And the file is unchanged

  Scenario: Competing writers preserve every accepted update
    Given writers share a notebook
    When they create decisions concurrently in a missing notebook
    Then every decision is retained in a valid notebook
    When they replace a note using the same expected revision
    Then exactly one replacement succeeds and the others report revision conflicts

  Scenario: Resume a decision from a bounded recent list
    Given several local decisions
    When I list decisions with a limit and offset
    Then the most recently created decisions appear first in deterministic order
    And totals and pagination are explicit without creating or changing storage

  Scenario: Separate processes share one notebook safely
    Given several operating-system processes use the same notebook path
    When they create the notebook simultaneously, or revise one note with the same expected revision
    Then every started decision is kept in one intact notebook
    And exactly one replacement succeeds while the others report revision conflicts

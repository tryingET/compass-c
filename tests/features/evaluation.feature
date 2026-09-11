Feature: Inspect frozen paired host evidence without overstating its meaning
  The operator can compare complete scored A/A or A/B observations against a
  frozen corpus. Development cases remain author-visible and synthetic fixtures
  never become evidence of actual model behavior or permission to act.

  Scenario: Report paired quality and routing changes
    Given a frozen corpus with positive, negative, overlap and pressure cases
    And one scored baseline and candidate observation for every case
    When the operator evaluates the paired observations
    Then the report includes case, criterion and routing pass rates and paired deltas
    And it names every criterion and routing regression
    And it reports exact two-sided sign-test uncertainty over discordant case pairs

  Scenario: Measure A/A disagreement before interpreting A/B improvements
    Given two complete observation sets for the same host and revision
    When the operator evaluates an A/A comparison
    Then disagreement remains visible even if the net pass-rate change is zero
    And the report makes no claim that a candidate improved behavior

  Scenario: Preserve evidence boundaries and provenance
    Given synthetic scores on the author-visible development corpus
    When the operator evaluates the observations
    Then the report labels the scores synthetic and the corpus author-visible
    And it preserves the corpus fingerprint, host, grader and arm revisions
    And the report does not grant action permission

  Scenario Outline: Reject incomplete or incompatible evidence
    Given paired observations with <defect>
    When the operator evaluates the observations
    Then evaluation fails with an INVALID_INPUT contract error
    Examples:
      | defect                                  |
      | a changed corpus fingerprint            |
      | missing, duplicate or unknown cases     |
      | missing, duplicate or unknown criteria  |
      | non-boolean scores or selection         |
      | missing host, revision or response refs |
      | oversized or invalid Unicode run text  |
      | an A/A comparison of different revisions|

  Scenario: Summarize supplied evidence without changing it
    Given valid frozen corpus and scored observations
    When the operator evaluates the observations twice
    Then both reports are equal
    And neither input is changed
    And action_permission is not_granted

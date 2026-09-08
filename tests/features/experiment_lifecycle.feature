Feature: A resumable experimental decision partner
  The owner freezes a sourced finite model and bounded candidate protocols in a local decision.
  COMPASS-C retains the experiment lifecycle without executing a protocol or granting permission.

  Scenario: Resume a bounded plan in a fresh process
    Given a saved model, experiment candidates, bounds and explicit current evidence dependencies
    When the owner resumes the saved plan
    Then the original inputs and calculated branches remain exact and inspectable
    And the summary identifies current winners and the next advisory step

  Scenario: Preview and atomically incorporate a sourced result
    Given a saved informative experiment and dependent recommendation
    When the owner previews an explicitly identified sourced observation
    Then the posterior and affected recommendations appear without a write
    When the owner applies that observation at the current decision revision
    Then one transaction retains the prior, observation, posterior and replacement history
    And old model reasoning and dependent recommendations become stale
    And the decision revision advances once

  Scenario: A lost response does not double count evidence
    Given an observation that was already incorporated
    When the identical event is retried with the old revision
    Then its original receipt is returned without another update
    And changed reuse of that event or reuse in another plan fails explicitly

  Scenario: Ordinary evidence updates make old plans obsolete
    Given an experiment plan depending on a recorded evidence note
    When that evidence is revised
    Then the plan requires replanning
    And a result cannot silently update its stale model

  Scenario: Failure is atomic and malformed state fails closed
    Given an impossible observation, stale revision, malformed input or contradictory stored history
    When a lifecycle operation is attempted
    Then it fails with a stable error
    And no partial notes, observations or revision changes are committed

  Scenario: Existing notebooks require an explicit lifecycle migration
    Given a valid schema-1 or schema-2 notebook
    When the owner reads or uses an older supported operation
    Then the schema remains unchanged
    And lifecycle writes require an explicit transactional migration

Feature: Explicit experiment storage upgrade without legacy regression
  A local notebook retains its existing behavior until its owner requests migration.
  Persisted experiment plans and observations require verified schema 3 storage.

  Scenario: Existing notebooks remain usable without a silent upgrade
    Given a frozen schema 1 or schema 2 notebook with historical evidence
    When the owner reads, starts another decision, or uses a previously supported operation
    Then the notebook keeps its original schema version and historical evidence
    And schema 2 revisions and evidence updates remain available
    But the new experiment lifecycle requests an explicit migration

  Scenario: The owner explicitly upgrades an existing notebook
    Given a valid schema 1 or schema 2 notebook
    When the owner migrates it
    Then its version becomes 3 and experiment storage is added
    And every decision, note, invalidation, and revision remains intact
    And migrating it again makes no further changes

  Scenario: An upgrade fails after schema creation begins
    Given a legacy notebook whose metadata update is refused
    When the owner requests migration
    Then the whole upgrade rolls back, including newly created tables
    And the notebook remains byte-for-byte unchanged

  Scenario: Corrupt history or experiment schema is not adopted
    Given malformed legacy history or schema 3 storage missing observation uniqueness
    When the owner reads or migrates the notebook
    Then the notebook fails with a stable invalid-storage error
    And no partial repair or migration is written

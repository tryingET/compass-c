Feature: Opt in to sourced evidence updates without background monitoring
  A local decision owner supplies an explicit evidence batch, inspects its effects,
  and chooses whether to apply it. COMPASS-C never fetches sources or interprets
  reversal conditions as authorization.

  Scenario: Preview an evidence batch before opting in
    Given a decision contains sourced evidence, dependent reasoning, a recommendation,
      reversal conditions, and recorded outcomes
    When I preview a supplied replacement batch at its current revision
    Then I see the exact replacement claims, sources, and combined invalidation impact
    And exact reversal conditions and outcome notes remain available for explicit review
    And no condition is automatically evaluated and no source is fetched or verified
    And the decision and database bytes are unchanged

  Scenario: Apply a valid batch as one revision
    Given two independent evidence notes and their dependent reasoning
    When I explicitly apply sourced replacements at the current revision
    Then both replacements are appended in one transaction and one revision
    And every original claim, source, and dependency remains in history
    And affected reasoning and previous recommendations are invalidated
    And every replacement has a matching revision and invalidation history entry
    And permission for external actions is not granted

  Scenario: Reject any unsafe member without partial writes
    Given a batch with one valid replacement and one invalid replacement
    When I preview or apply the batch
    Then the entire batch fails with a stable error
    And no note, history entry, or revision change is persisted
    And malformed fields, unsourced observations, superseded notes, conflicting roots,
      and dependencies invalidated elsewhere in the batch are rejected

  Scenario: A preview does not authorize a later stale write
    Given a batch was previewed at an earlier decision revision
    And another writer has changed the decision
    When I try to apply the earlier batch at its preview revision
    Then the operation reports a revision conflict without changing the current state

  Scenario: Recover from a storage failure without partial history
    Given a valid replacement batch
    And storage rejects a later history insertion
    When I apply the batch
    Then the transaction rolls back every replacement, invalidation, and revision change

  Scenario: Competing batch writers preserve optimistic concurrency
    Given several writers share the same decision and expected revision
    When they concurrently apply evidence batches
    Then exactly one complete batch succeeds
    And all other writers receive revision conflicts

  Scenario: Existing storage must be usable and explicitly migrated
    Given missing, malformed, or schema-1 notebook storage
    When I preview or apply an evidence update
    Then no file is silently created, repaired, or migrated
    And schema-1 storage requests explicit migration

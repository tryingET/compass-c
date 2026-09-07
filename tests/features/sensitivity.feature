Feature: Inspect when uncertainty changes the expected-value preference
  The decision owner supplies both probability endpoints and comparable payoffs.
  COMPASS-C reports conditional arithmetic without choosing a decision criterion
  or granting permission to act. Executable scenarios are in test_sensitivity.py.

  Scenario: Find every preference reversal along a supplied probability path
    Given three actions with payoffs [12, 0], [9, 9], and [0, 12]
    And probability endpoints [1, 0] and [0, 1]
    When the owner requests sensitivity
    Then the preference changes at t = 0.25 and t = 0.75
    And every open interval has the correct expected-value winner
    And both tied actions are retained at each breakpoint

  Scenario: Preserve disagreement and endpoint ties
    Given actions with identical expected values throughout the path
    When the owner requests sensitivity
    Then every tied action remains a winner in input order
    And ties that occur only at an endpoint are reported at that endpoint

  Scenario: Ignore a crossing that cannot affect the preference
    Given two inferior actions exchange rank below an unchanged best action
    When the owner requests sensitivity
    Then no preference breakpoint is reported

  Scenario: Preserve narrow preference intervals and large-payoff differences
    Given bounded payoffs whose winning intervals are very narrow
    And large bounded payoffs with small decision-relevant differences
    When the owner requests sensitivity
    Then no real preference interval or preference difference is discarded
    And exact rational path coordinates preserve intervals smaller than float precision

  Scenario: Do not manufacture a probability model or authority
    Given the owner supplies only one probability endpoint or an invalid model
    When the owner requests sensitivity
    Then the request fails with INVALID_INPUT
    And successful requests always disclose the model assumptions
    And no calculation chooses a criterion or grants action permission

  Scenario: Comparison and sensitivity agree on exact decimal ties
    Given decimal payoffs whose expected values or maximum regrets are equal
    When the owner requests comparison and sensitivity on that model
    Then rounded arithmetic cannot invent a preference
    And genuinely distinct expected values are still distinguished

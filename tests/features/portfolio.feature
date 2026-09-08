Feature: Coordinate decisions without erasing disagreement or transferring authority
  The owner supplies total shared resource capacities, dependencies, exclusions,
  stakeholder-specific values of committing and deferring, and reversal conditions.
  COMPASS-C enumerates bounded feasible portfolios and exposes tradeoffs without
  selecting moral weights, a portfolio, a schedule, or permission to act.
  Executable scenarios are in test_portfolio.py.

  Scenario: Respect shared resources and precedence together
    Given a foundation uses 2 days and its dependent rollout uses 3 days
    And the portfolio has 5 days available
    When the owner compares portfolios
    Then rollout without the foundation is infeasible
    And the combined portfolio orders foundation before rollout
    And reducing capacity to 4 days makes the combined portfolio infeasible

  Scenario: Preserve incompatible stakeholder preferences
    Given two mutually exclusive choices favor different stakeholders
    When the owner compares portfolios
    Then both choices remain on the nondominated frontier
    And each stakeholder's preferred portfolio is visible
    And no common optimum or weighted compromise is invented

  Scenario: Value explicitly modeled deferral and preserve reversal conditions
    Given committing an option has values [8, 1]
    And deferring it has supplied option values [2, 6]
    And the owner supplies a reversal condition for commitment
    When the owner compares portfolios
    Then committing and deferring are both nondominated
    And committed and deferred values are reported separately
    And the reversal condition remains visible

  Scenario: Preserve ties and exact decimal capacity boundaries
    Given two choices each have equal stakeholder values
    And resource requirements 0.1 and 0.2 exactly fit capacity 0.3
    When the owner compares portfolios
    Then the combined portfolio is feasible
    And exact decimal values preserve ties without adding stakeholder weights

  Scenario: Expose impossible choices without inventing a workaround
    Given a choice requires an option with which it is mutually exclusive
    When the owner compares portfolios
    Then no feasible portfolio contains that choice
    And it is reported as unavailable under the supplied constraints

  Scenario: Reject invalid or unbounded models before enumeration
    Given a model has cyclic or unknown dependencies, invalid resource names,
      missing stakeholder values, nonfinite numbers, or more than 10 decisions
    When the owner compares portfolios
    Then the request fails with INVALID_INPUT
    And the caller's model remains unchanged

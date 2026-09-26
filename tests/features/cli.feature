Feature: A complete standalone decision workflow
  COMPASS-C must work from the library, installed CLI, and portable skill without
  Agent Kernel, a network connection, or a model provider.

  Scenario: Resume and revise a consequential decision
    Given a local decision with sourced evidence, alternatives, and reversal conditions
    When I resume it in a fresh process and request its brief
    Then I can inspect the recommendation, provenance, uncertainty, and revision
    When I replace evidence with a reason using the expected revision
    Then the old evidence remains inspectable and affected recommendations become stale
    And the brief requests reconsideration without granting action permission

  Scenario: Inspect sensitivity without saving anything
    Given an explicitly supplied payoff matrix and two probability vectors
    When I calculate sensitivity from the CLI
    Then the preference boundary and ties are inspectable
    And no notebook directory is created

  Scenario: Fail clearly on malformed evaluation input
    Given an invalid or missing evaluation file
    When I request an evaluation report
    Then the CLI returns a bounded machine-readable error without a traceback
    And it does not create a notebook

  Scenario: Name every supported calculation when a kind is unknown
    Given a library or MCP caller supplies an unsupported calculation kind
    When the calculation is requested
    Then it fails with a stable unknown-calculation error
    And the message names every kind the CLI accepts and the calculator reference documents
    And no notebook directory is created

  Scenario: Use the documented default notebook without an explicit path
    Given neither --db nor COMPASS_DB is supplied
    When the CLI starts a decision
    Then the notebook is created at .compass/decisions.sqlite3 in the working directory
    And nothing is written under the home directory

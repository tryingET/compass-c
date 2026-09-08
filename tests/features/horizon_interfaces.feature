Feature: Full-horizon operations through standalone interfaces
  Every supported interface exposes the same bounded advisory operations.
  A caller can preview evidence changes before explicitly applying them.

  Scenario: An installed CLI user discovers note vocabulary without reading source
    Given no notebook and no access to source implementation
    When I request record or revise help
    Then accepted note statuses and the default proposed status are visible
    And record help lists accepted note kinds including reversal conditions
    And no notebook is created

  Scenario Outline: Portfolio analysis preserves disagreement without creating storage
    Given an absent notebook and one decision valued differently by two stakeholders
    When I calculate its portfolio through <interface>
    Then both stakeholder preferences remain visible
    And the tool chooses no compromise or external action
    And no notebook is created
    Examples:
      | interface |
      | package CLI |
      | portable CLI |
      | MCP client |

  Scenario Outline: Evidence updates require an explicit apply
    Given a sourced observation and a recommendation depending on it
    When I submit replacement evidence through <interface> without applying it
    Then the preview shows the affected recommendation
    And the stored revision remains unchanged
    When I explicitly apply the same update at the observed revision
    Then the old observation and recommendation remain in history as stale
    And the updated observation retains its source
    Examples:
      | interface |
      | package CLI |
      | portable CLI |
      | MCP client |

  Scenario Outline: Experimental analysis is available without notebook state
    Given a finite decision model and an informative bounded experiment
    When I propose the experiment and supply a sourced result through <interface>
    Then the result exposes the original and updated model and conditional choices
    And no experiment is executed or notebook silently created
    Examples:
      | interface |
      | package CLI |
      | portable CLI |
      | MCP client |

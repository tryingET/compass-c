Feature: Optional Agent Kernel scope projections
  A standalone checkout validates the scope snapshots it actually contains.
  The absence of snapshots does not assert anything about live Agent Kernel state.

  Scenario Outline: There are no task-scope snapshots to validate
    Given a checkout whose task-scope directory is <directory_state>
    And no Agent Kernel executable is available
    When I run the task-scope snapshot check
    Then the check succeeds with "ok: no task-scope snapshots to validate"
    And no Agent Kernel state is read or created

    Examples:
      | directory_state               |
      | absent                        |
      | empty                         |
      | contains only unrelated files |

  Scenario: Existing snapshots still require Agent Kernel authority
    Given a checkout containing an AK task-scope snapshot
    And no Agent Kernel executable is available
    When I run the task-scope snapshot check
    Then the check fails because Agent Kernel is unavailable
    And the check does not report a validated snapshot

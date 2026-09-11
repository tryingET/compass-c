Feature: Resume an experiment through each standalone interface
  A saved experiment makes its frozen model, explicit observations, and revised
  decision inspectable without reconstructing an earlier chat. It remains advisory.

  Scenario Outline: Cold resume and observe a bounded saved experiment
    Given a decision with a frozen finite model and an informative bounded experiment
    When I save the experiment through <interface>
    Then the compact response identifies the plan, decision revision, and next step
    And a new client can discover and resume the same frozen plan
    When I preview a sourced observation from a bounded JSON file or object
    Then the preview identifies the possible model revision without changing the database
    When I explicitly apply the observation once
    Then the posterior and prior remain inspectable through the resumed plan
    And dependent recommendations are stale in the decision brief
    And replaying the identical event does not count the evidence twice
    And a conflicting reuse of the event identity fails without changing the database
    And no result grants action permission or claims to verify the supplied source
    Examples:
      | interface |
      | package CLI |
      | portable CLI |
      | MCP client |

  Scenario Outline: Malformed file input cannot initialize or mutate a notebook
    Given an absent notebook
    When I supply unreadable, malformed, duplicate-key, nonfinite, or oversized input to <interface>
    Then the CLI returns its stable JSON error envelope
    And no notebook is created
    Examples:
      | interface |
      | package CLI |
      | portable CLI |

  Scenario: MCP discovery preserves local advisory and read-only boundaries
    Given an absent notebook and a real local MCP connection
    When I discover the lifecycle tools
    Then resume, list, and preview tools are marked read-only
    And saving and explicitly applying are marked local writes
    And fractional, boolean, and string revision values are rejected
    And discovery and invalid calls do not create a notebook

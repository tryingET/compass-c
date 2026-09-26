Feature: Supported local MCP decision workflow
  The pinned SDK connects to the packaged COMPASS-C adapter over actual stdio.
  Local SDK verification is not vendor-host installation or behavioral evidence.

  Scenario: Discover the installed adapter outside the checkout
    Given COMPASS-C with its MCP extra is installed
    When an SDK client initializes a stdio session from an unrelated directory
    Then it discovers all notebook and calculation tools
    And read and local-write hints describe the tool boundaries
    And no notebook exists until a valid start request

  Scenario: Read and calculate without creating a notebook
    Given a configured notebook path does not exist
    When the client calculates or attempts to read, list, review, or brief a decision
    Then calculations return conditional results and reads return stable errors
    And neither the notebook nor its parent directory is created

  Scenario: Recover, inspect, and revise a local decision
    Given a decision contains evidence and a dependent recommendation
    When the client reopens its session and lists decisions
    Then it can recover the existing decision without duplicating it
    When the client revises evidence using the expected revision
    Then the brief shows the new provenance and the stale recommendation
    And the history preserves the prior evidence and the replacement reason
    And a stale revision fails without writing a second replacement
    And every result remains advisory

  Scenario: Preserve storage and report failures as structured data
    Given a configured path is blocked or contains unrelated SQLite data
    When the client requests a notebook operation
    Then it receives a stable domain error envelope without a traceback
    And unrelated data is unchanged

  Scenario: Print a portable configuration
    Given an explicit Python interpreter and notebook path
    When the local configuration helper runs
    Then the configuration invokes the installed compass_c.mcp_server module
    And it preserves the virtual environment interpreter path
    And no host settings or notebook files are written

  Scenario: Reject malformed revision types before writing
    Given a decision has revision one
    When a client supplies true, 1.0, or "1" as the expected revision
    Then the request is rejected without converting the value to an integer
    And the decision and its revision are unchanged

  Scenario: Use the documented default notebook when COMPASS_DB is absent
    Given the server is launched without COMPASS_DB
    When a client starts a decision
    Then the notebook is created at .compass/decisions.sqlite3 in the home directory
    And nothing is written under the server's working directory
    But a CLI started in another directory without --db or COMPASS_DB uses a different notebook

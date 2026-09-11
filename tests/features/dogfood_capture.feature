Feature: Frozen executable aliases remove capture path transcription
  A capture helper resolves short executable names from the frozen run manifest.
  It preserves the exact launched command and every attempted operation.

  Scenario Outline: A short target selects the exact frozen executable
    Given a manifest naming the isolated installed executable
    When I capture a command using <alias>
    Then only the first argument is replaced using <manifest_key>
    And the requested argv, launched argv, and manifest fingerprint are retained
    And all remaining arguments and the actual process output are unchanged
    And PATH cannot substitute another executable for the alias
    Examples:
      | alias | manifest_key |
      | compass-c | installed_cli |
      | installed-python | installed_python |

  Scenario: A misspelled path remains a counted launch failure
    Given an executable path with a transcription error
    When I capture that exact target
    Then the helper does not correct it or retry
    And one attempted operation retains the original target and launch error

  Scenario: A broken manifest cannot select an arbitrary fallback
    Given an alias and a missing or invalid frozen manifest target
    When I capture the command
    Then no target process is launched
    And one attempted operation records the resolution failure and requested argv
    And no actual argv is invented

  Scenario: Child failure and timeout costs remain visible
    Given a captured target that fails or times out
    When its process result is retained
    Then its status, stdout, stderr, byte sizes and timing remain recorded
    And each attempted operation contributes one trace entry
    And no output file is silently replaced

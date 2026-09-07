Feature: Preview installation with the requested publication assurance
  A dry run never installs, replaces, stages, or creates destination directories.
  A supplied repository and commit still require public-head content verification.
  Executable scenarios are in test_installer_verification.py.

  Scenario: Preview a named publication
    Given the operator supplies a repository and full commit identity
    When the operator requests an installation dry run
    Then the published skill is verified against the local source
    And the destination is returned without filesystem changes

  Scenario: Fail closed when publication verification fails
    Given the supplied publication differs from the local skill or cannot be verified
    When the operator requests an installation dry run
    Then the verification error is returned
    And no destination, staging directory, lock, or receipt is created

  Scenario: Preview a local installation offline
    Given no publication identity is supplied
    When the operator requests an installation dry run
    Then no publication verification is requested
    And no filesystem changes occur

  Scenario: Preserve replacement permission requirements
    Given a skill already exists at the destination
    When the operator requests a replacement dry run without a permission record
    Then the request is rejected before publication verification
    And the existing skill is preserved
    But a replacement dry run with a permission record verifies the named publication
    And still preserves the existing skill

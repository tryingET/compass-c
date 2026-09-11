Feature: Distribute only explicitly declared COMPASS-C source files
  Building an archive must not disclose unrelated local material. The source
  toolkit remains self-contained and rebuildable after extraction without Git.

  Scenario: Build from a working checkout containing private local files
    Given tracked runtime, documentation, repo skill and vendored tooling
    And untracked notes, credentials, caches and files inside the portable skill
    When I build all three archives
    Then only declared distribution files are packaged
    And the toolkit retains the repo skill and required vendored tooling
    And tracked source edits are preserved

  Scenario: Exclude unsafe material even when accidentally tracked
    Given tracked secret keys, runtime state, receipts, caches or symlinked paths
    When I build an archive
    Then none of that material enters the archive

  Scenario: Rebuild an extracted source toolkit without Git
    Given a source toolkit was extracted and its manifest declares its files
    And unrelated local notes have been added after extraction
    When I rebuild the toolkit
    Then the same declared sources produce byte-identical archives
    And the added local notes are excluded

  Scenario: Retain runnable toolkit commands after extraction
    Given the toolkit includes Python helpers and shell validation wrappers
    When I build an archive
    Then its Unix file metadata keeps those commands executable
    And ordinary source documents remain non-executable

  Scenario: Refuse an undeclared or unsafe source tree
    Given neither a repository index nor a valid distribution manifest is available
    Or a distribution manifest attempts path traversal
    When I request an archive build
    Then the builder refuses instead of sweeping the local directory

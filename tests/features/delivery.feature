Feature: Local delivery workflow
  Scenario: Reject staged whitespace
    Given an isolated repository with the delivery files
    When trailing whitespace is staged
    Then make check fails

  Scenario: Reject unstaged whitespace
    Given an isolated repository with the delivery files
    When trailing whitespace remains unstaged
    Then make check fails

  Scenario: Install the local validation environment
    Given an isolated repository with the delivery files
    When make install runs
    Then a working local Python environment exists

  Scenario: Build a portable delivery bundle
    Given an isolated repository with the delivery files
    When make build runs twice
    Then identical archives contain all delivery helpers and no local config

  Scenario: Require an explicit publication destination
    Given an isolated repository with the delivery files
    When make publish runs without a destination
    Then publication fails without creating an artifact

  Scenario: Publish to a local destination
    Given an isolated repository with the delivery files
    When make publish runs with a temporary local destination
    Then the published artifact equals the built bundle

  Scenario: Clean generated files without deleting local configuration
    Given an isolated repository with generated files, Python caches and local configuration
    When make clean runs
    Then generated files are removed and local configuration is preserved

  Scenario: Reject a missing Codex merge gate
    Given an isolated repository with the delivery files
    When the PR helper loses its Codex review requirement
    Then make check fails

  Scenario: Reject a missing human-only main rule
    Given an isolated repository with the delivery files
    When the PR helper loses its human-only main requirement
    Then make check fails

  Scenario: Reject a mismatched branch type contract
    Given an isolated repository with the delivery files
    When the PR helper omits an allowed work branch type
    Then make check fails

  Scenario: Reject a failing behavioral suite before commit
    Given an isolated repository with a failing workflow test
    When make check runs
    Then the workflow failure blocks the commit gate

  Scenario: Reject a missing complete-review lifecycle contract
    Given an isolated repository with the delivery files
    When the PR helper loses its wait-for-all-reviewers requirement
    Then make check fails

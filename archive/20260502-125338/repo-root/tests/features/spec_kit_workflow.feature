Feature: Deterministic spec-kit orchestration

  Scenario: Build deterministic plan and publish in dry-run mode
    Given a valid spec submission with dependencies
    When the workflow runs with approval granted
    Then execution order is deterministic
    And parallel groups are produced
    And issue drafts are generated

  Scenario: Deny publication when approval is rejected
    Given a valid spec submission with dependencies
    When the workflow runs with approval denied
    Then publication is blocked

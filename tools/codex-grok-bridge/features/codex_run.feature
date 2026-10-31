Feature: Offline Codex run specification and usage

  # Executed by RunTest.test_spec_once and test_concurrent_spec_allows_one_launch
  Scenario: Reserve a request once
    Given a valid request
    When its spec is requested twice or concurrently
    Then exactly one caller may launch and the stored spec is unchanged

  # Executed by RunTest.test_all_fields and test_documented_exec_fields_missing_cache_write
  Scenario: Preserve unknown telemetry
    Given synthetic exec JSON events
    When usage is parsed without a cache-write count
    Then cache_write is null and completeness is partial

  # Executed by RunTest.test_cancelled_retains_usage
  Scenario: Keep usage after cancellation
    Given complete usage events followed by cancellation or a truncated final event
    When usage is parsed
    Then known usage remains and completeness is partial

  # Executed by RunTest.test_join_pricing_uses_ledger_subscription_semantics
  Scenario: Separate estimated and billed cost
    Given a matching priced ledger row with dated models.dev provenance
    When usage is joined to that row
    Then ledger cost selection applies and unknown billed cost stays null

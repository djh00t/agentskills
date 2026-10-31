Feature: Best-effort post-send wake

  # Executed by WakeTests.test_missing_items_disable_once
  Scenario: Missing Keychain items disable the wake
    Given either or both mocked Keychain items are absent
    When a successful send is passed to the wake helper
    Then no HTTP request occurs and one disabled line is emitted
    And the original send result is returned unchanged

  # Executed by WakeTests.test_success_posts_only_routing_fields
  Scenario: Send only routing fields
    Given both mocked Keychain items exist
    When a successful send is passed to the wake helper
    Then exactly one authenticated POST contains only conversation_id and seq
    And HTTP uses a five-second timeout

  # Executed by WakeTests.test_http_failures_do_not_change_send
  Scenario: Do not retry HTTP failures or redirects
    Given a mocked HTTP failure or redirect
    When the wake is attempted
    Then one status-only failure line is emitted without retry
    And the send result is unchanged

  # Executed by WakeTests.test_exception_details_never_escape
  Scenario: Keep credentials out of observable output
    Given a mocked transport exception contains sentinel credentials
    When the wake is attempted
    Then no exception escapes and output contains no credentials
    And no files are written in the temporary directory

  # Executed by WakeTests.test_cli
  Scenario: Invoke the post-send helper from the command line
    Given conversation and sequence arguments
    When the CLI runs after a confirmed send
    Then it invokes the wake helper with those routing fields

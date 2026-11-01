Feature: Read-only inbox routing plan
  Scenario: Page from the handled cursor and skip recorded messages
    Given an atomic log with handled messages
    When the inbox reads overlapping pages
    Then new Codex messages appear once in sequence order
    # Executed by InboxTest.test_pages_filter_and_order and test_paging_duplicates_cycles_and_cap

  Scenario: Inspect legacy and pending state without writes
    Given a legacy cursor or received-but-unrouted message
    When the inbox builds a plan
    Then handled messages are skipped and pending messages resurface without locks
    # Executed by InboxTest.test_snapshot_and_legacy_are_read_only and test_pending_resurfaces

  Scenario: Flag decisions and malformed input without authorization
    Given decisions, parse warnings, sensitive terms, and invalid messages
    When the inbox builds a plan
    Then warnings and owner flags remain visible and valid messages continue
    # Executed by InboxTest.test_owner_flags_warnings_and_excerpt and test_bad_messages_do_not_abort

  Scenario: Evaluate expiry once in epoch seconds
    Given expiry at, before, or after the current time and invalid expiry values
    When the inbox builds a plan
    Then every entry has an expiry flag and invalid values become errors
    # Executed by InboxTest.test_expiry_boundary_and_clock_once

  Scenario: Validate the CLI and reader boundary
    Given missing readers, malformed pages, or an optional roster
    When the inbox runs
    Then invalid arguments fail clearly and valid runs leave the directory unchanged
    # Executed by InboxTest.test_invalid_pages, test_optional_roles_and_load_once,
    # test_cli_arguments_and_legacy, test_cli_success_and_failure_leave_directory_unchanged,
    # and test_no_mutating_calls

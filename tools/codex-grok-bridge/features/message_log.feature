Feature: Durable forward-only message log

  # Executed by MessageLogTest.test_migrate_legacy_cursor
  Scenario: Persist a canonical legacy cursor
    Given a legacy cursor containing "097"
    When the cursor is read and the legacy file is removed
    Then a new log reader returns 97 and the stored sequence is "97"

  # Executed by MessageLogTest.test_cursor_starts_before_first_received_sequence
  Scenario: Stop the cursor before an unrouted sequence
    Given sequence 4 is received and sequence 5 is routed
    When the cursor is read
    Then the cursor is 3

  # Executed by MessageLogTest.test_skipped_and_unknown_transitions_fail
  Scenario: Reject a skipped state
    Given sequence 1 is received
    When a transition directly to acked is attempted
    Then LogError is raised

  # Executed by MessageLogTest.test_escaping_round_trip_and_metadata
  Scenario: Preserve escaped text and transition metadata
    Given text fields contain tabs, quotes, newlines, and Unicode
    When a record is stored and then routed with acknowledgement metadata
    Then all text and metadata are recovered exactly

  # Executed by MessageLogTest.test_corrupt_sequences_duplicates_and_states
  Scenario: Reject corrupt persisted rows
    Given a log contains an invalid sequence, duplicate sequence, or unknown state
    When a read, record, or transition is attempted
    Then LogError is raised and the log bytes remain unchanged

  # Executed by MessageLogTest.test_log_and_lock_mode_are_private
  Scenario: Create private log and lock files
    Given a permissive process umask
    When a record is stored and routed
    Then the log and lock file modes are 0600

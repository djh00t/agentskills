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

  # Executed by MessageLogTest.test_record_rejects_cursor_rollback
  Scenario: Reject records at or below the cursor
    Given a non-empty log or a legacy cursor of 97
    When a record at or below the current cursor is attempted
    Then LogError is raised without changing the log

  # Executed by MessageLogTest.test_existing_log_ignores_legacy_unless_higher
  Scenario: Keep the existing log authoritative
    Given a log cursor of 3 without a migration marker
    When a legacy cursor is read beside the log
    Then values at or below 3 are ignored and higher values raise LogError

  # Executed by MessageLogTest.test_migration_marker_cannot_be_forged_or_changed
  Scenario: Reserve the migration marker
    Given the migration note is reserved for internal use
    When a public write attempts to create or change a migration marker
    Then LogError is raised

  # Executed by MessageLogTest.test_first_legacy_value_must_be_complete
  Scenario: Reject an incomplete first legacy cursor
    Given a missing log and a partial or unterminated legacy value
    When a cursor read or record is attempted
    Then LogError is raised and no log is created

  # Executed by MessageLogTest.test_write_syncs_file_then_directory
  Scenario: Sync the file and its directory
    Given a new message record
    When the log is replaced
    Then the file descriptor is synced before the directory descriptor

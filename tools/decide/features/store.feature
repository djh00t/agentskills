Feature: decide event store

  Scenario: a group-readable home dir is refused
  Scenario: the first event points at 64 zeros
  Scenario: each event hashes the previous line
  Scenario: append outside the lock is refused
  Scenario: verify-log passes on an untouched log
  Scenario: verify-log finds an edited line
  Scenario: verify-log finds a deleted line
  Scenario: verify-log finds a non-canonical line
  Scenario: events.jsonl is created with mode 0600
  Scenario: two processes appending at once never break the chain

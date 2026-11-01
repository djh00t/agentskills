Feature: Derived SQLite index

  Scenario: rebuild creates the index with mode 0600
  Scenario: a stale index is rebuilt on read
  Scenario: an index with the right seq but a different last hash is rebuilt
  Scenario: an index missing head metadata is rebuilt
  Scenario: the index matches a fresh fold
  Scenario: a deleted index is recreated
  Scenario: rebuild command reports index summary

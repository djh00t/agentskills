Feature: decide command line

  Scenario: version prints the tool and schema version
  Scenario: an unknown command is a usage error
  Scenario: a module that defines register adds a command
  Scenario: a DecideError becomes its exit code and a stderr message
  Scenario: home_dir fails closed when no home is given
  Scenario: parse_iso rejects a time without an offset
  Scenario: DECIDE_NOW overrides the clock

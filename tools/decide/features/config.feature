Feature: Private configuration and file masking

  Scenario: the sample config loads
  Scenario: roster names come from the name line
  Scenario: a page_summary without {waiting} exits 5
  Scenario: a missing config exits 5
  Scenario: an unknown config key exits 5
  Scenario: a roster with no ids exits 5
  Scenario: a bad private regex exits 5 without echoing it
  Scenario: an account number is masked to its last three digits
  Scenario: a private surname is masked
  Scenario: a generic hit is masked by pattern name
  Scenario: mask_obj masks nested strings and keys
  Scenario: lint-files reports file line and pattern but not the value
  Scenario: lint-files exits 2 on a hit and 0 when clean
  Scenario: lint-files needs a config
  Scenario: invalid configuration rules fail without exposing values
  Scenario: private files and roster ids are validated
  Scenario: normalized values are masked and JSON reports never echo matches
  Scenario: roster names stay within their entry and default to the id
  Scenario: roster paths cannot escape or use symlinks
  Scenario: oversized fields and lines fail closed

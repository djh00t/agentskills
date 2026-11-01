Feature: Generic text linting

  Scenario: a GitHub token is found
  Scenario: an OpenAI-style key is found
  Scenario: an AWS key id is found
  Scenario: a private key header is found
  Scenario: a personal email is found
  Scenario: a noreply GitHub email is allowed
  Scenario: a home path is found
  Scenario: a 30-character key near the word pushover is found
  Scenario: a webhook URL is found
  Scenario: a nine-digit number is found
  Scenario: a 40-hex commit sha is not a long number
  Scenario: lint_request names the field path
  Scenario: the hit report never contains the matched text
  Scenario: ids and numbers in a PR field are not text
  Scenario: normalized and wrapped secrets are found
  Scenario: private key blocks and noreply suffixes are found
  Scenario: unknown nested text fields are scanned
  Scenario: long nonmatching fields are scanned quickly

Feature: event, answer and legacy schemas

  Scenario: an event with an unknown type is invalid
  Scenario: only page_ack and counter_floor may have a null id
  Scenario: prev_sha256 must be 64 hex characters
  Scenario: an event timestamp must be UTC with Z
  Scenario: an answer with an invalid recorder is invalid
  Scenario: a judgement mapping cannot be custom
  Scenario: blank words are invalid
  Scenario: closes ids must be distinct
  Scenario: a legacy record needs only id kind title and state
  Scenario: a legacy short head sha is allowed
  Scenario: free text rejects unsafe characters and uses normalized length
  Scenario: unknown fields do not echo input
  Scenario: identifiers reject trailing newlines
  Scenario: validation rejects invalid boundaries
  Scenario: event and answer boundaries are enforced
  Scenario: free text rejects invisible and overlong raw values
  Scenario: free text requires strings
  Scenario: invalid choice and label report both errors
  Scenario: raw non printable text is rejected after normalization

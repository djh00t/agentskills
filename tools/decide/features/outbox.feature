Feature: reply outbox

  Scenario: an answer queues one requester line at priority true
  Scenario: each cc gets an FYI line at priority false
  Scenario: an expired item tells the requester at priority false
  Scenario: a legacy item with no requester queues only cc lines
  Scenario: mark-sent removes the line from pending
  Scenario: mark-sent twice exits 3
  Scenario: an unknown oid exits 4
  Scenario: text is the exact template

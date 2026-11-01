Feature: requester state changes
  Scenario: withdraw closes a ready item
  Scenario: withdraw on a closed item exits 3
  Scenario: hold moves a shown item to on_hold
  Scenario: release sends a simple item back to ready
  Scenario: release sends a pr_merge item back to open
  Scenario: confirm-merge closes an approved item as merged
  Scenario: confirm-merge needs a 40-hex sha
  Scenario: confirm-merge on a shown item exits 3
  Scenario: merge-failed closes an approved item
  Scenario: a token in a withdraw reason is rejected
  Scenario: requester reasons must be safe and at most 200 characters
  Scenario: requester commands reject an unknown item
  Scenario: requester commands reject a broken event log
  Scenario: reason and sha options are required

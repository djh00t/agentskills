Feature: item state and read commands

  Scenario: a new simple item starts ready
  Scenario: a new pr_merge item starts open
  Scenario: a simple item cannot be approved
  Scenario: a pr_merge item cannot go from open to approved
  Scenario: nothing leaves a closed state
  Scenario: an approved pr_merge item can only be merged or fail
  Scenario: write_transition keeps optional fields only when present
  Scenario: fold applies import and timestamp fields
  Scenario: get_item returns items and reports missing ids
  Scenario: fold refuses an event for an unknown item
  Scenario: status shows the answer words once answered
  Scenario: status by requester and key finds the item
  Scenario: status by missing requester and key exits 4
  Scenario: status requires requester and key together
  Scenario: status of a missing item exits 4
  Scenario: list --open hides closed items
  Scenario: a null page acknowledgement permits later writes
  Scenario: stale transitions are refused
  Scenario: illegal transition writes are refused
  Scenario: legacy states must be reachable for the kind
  Scenario: valid pr_merge legacy states load and set closed_at only when closed
  Scenario: broken logs are refused by reads

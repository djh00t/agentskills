Feature: decide request schema

  Scenario: the three sample requests are valid
  Scenario: a request with an unknown field is invalid
  Scenario: a title longer than 80 characters is invalid
  Scenario: a request needs exactly one recommended option
  Scenario: option labels must run A, B, C in order
  Scenario: approves_merge is only allowed on pr_merge
  Scenario: a pr_merge request needs exactly one approves_merge option
  Scenario: a pr_merge request needs a 40-hex head sha
  Scenario: a complex request needs chat_link and quote
  Scenario: a time without an offset is invalid
  Scenario: chase_at must be before expires_at
  Scenario: cc may not include the requester
  Scenario: an integer is not a boolean
  Scenario: every error is reported, not just the first
  Scenario: unsafe and invalid request values are rejected
  Scenario: required fields and time boundaries are enforced
  Scenario: normalized text length and UUID boundaries are enforced
  Scenario: spoofing and review boundaries are rejected

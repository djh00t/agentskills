Feature: FSM ledger capture
  Usage events must survive short-lived harness processes.

Scenario: Codex Stop captures in the background
  Given a configured project matrix
  When Codex Stop receives a usage event
  Then the hook succeeds and the matrix is rendered

Scenario: SessionEnd survives until the next Stop
  Given a configured project matrix
  When SessionEnd accepts a usage event
  Then the next Stop records it once and clears the pending queue

Scenario: CLI append renders after exit
  Given a configured project matrix
  When the append CLI exits after requesting a render
  Then a separate process renders the matrix

Scenario: Metered calls do not retry internal errors
  Given a metered callable with side effects
  When it raises TypeError after performing one side effect
  Then the exception propagates without calling it again

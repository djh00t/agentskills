Feature: Per-turn cost ledger
  Every Codex turn is reported with model, tokens, wall clock and API-rate cost.

Scenario: A turn sums its model calls and records wall clock
  Given a Codex rollout with one turn of two model calls and a task_complete
  When the ledger is generated
  Then the turn row sums input, cache-read and output tokens
  And wall_clock_s and ttft_s come from task_complete

Scenario: A call the fsm-ledger never priced is flagged, not guessed
  Given only one of the turn's calls has a priced fsm-ledger row
  When the ledger is generated
  Then est_cost_usd covers only the priced call
  And calls_unpriced is 1 and cost_complete is false

Scenario: A subscription-billed call is costed at API rates
  Given a priced fsm-ledger row with cost_is_plan true and api_equivalent_usd
  When the ledger is generated
  Then est_cost_usd uses api_equivalent_usd, not the plan amount

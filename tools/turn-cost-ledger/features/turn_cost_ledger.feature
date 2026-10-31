Feature: Per-turn cost ledger
  Every Codex turn is reported with model, tokens, wall clock and API-rate cost.

Scenario: A turn sums its model calls and records wall clock
  Given a Codex rollout with one turn of two model calls and a task_complete
  When the ledger is generated
  Then the turn row sums input, cache-read and output tokens
  And wall_clock_s and ttft_s come from task_complete

Scenario: A call the fsm-ledger never priced is flagged, not guessed
  Given only one of the turn's calls has a priced row written by fsm_ledger.ledger.append_dict
  And that row is keyed by event_id "codex:{session_id}:{response_id}"
  When the ledger is generated
  Then est_cost_usd covers only the priced call
  And calls_unpriced is 1 and cost_complete is false

Scenario: A subscription row uses api_equivalent_usd when present
  Given a billing_mode=subscription row written by append_dict with a numeric api_equivalent_usd
  When the ledger is generated
  Then est_cost_usd is the api_equivalent_usd and the turn is cost-complete

Scenario: A subscription row without api_equivalent_usd is unpriced, never $0
  Given a billing_mode=subscription row written by append_dict (costTotal 0, cost_is_plan true)
  When the ledger is generated
  Then calls_unpriced is 1 and cost_complete is false

Scenario: Malformed usage is skipped, not fatal
  Given a call whose token count is not a number and a call whose usage is not an object
  When the ledger is generated
  Then the bad count counts as 0 and the non-object usage is skipped

Scenario: --since takes an ISO date and filters by the rollout path date
  Given rollouts under 2026/10/30 and 2026/10/31
  When the ledger is generated with --since 2026-10-31
  Then only the 2026/10/31 turn is reported
  And a non-ISO --since value is rejected

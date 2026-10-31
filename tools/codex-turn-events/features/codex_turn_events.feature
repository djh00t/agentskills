Feature: Codex turn events
  Each Codex turn is logged locally and pushed to a webhook so the Chief of Staff
  does not have to poll. Webhook URL and key never touch disk or logs.

Scenario: Stop logs the turn and posts turn_complete
  Given a Codex rollout with one finished turn
  When the Stop hook runs with that turn's payload
  Then a turn row with model, tokens and exact wall clock is appended
  And a turn_complete event with session, task, status and PR URL is POSTed with the key
  And the hook prints {}
  And neither the URL nor the key is written to disk

Scenario: PermissionRequest posts needs_approval and starts the human-wait clock
  When the PermissionRequest hook runs
  Then a needs_approval event with tool name and description is POSTed
  And the local event row records wait_started_at

Scenario: A hook never fails the Codex turn
  Given an unreachable webhook or a malformed payload
  When the Stop hook runs
  Then it prints {} and records the failure without the URL

Scenario: Daily reconcile fills turns the hooks missed
  Given rollouts with one turn logged only approximately and one turn never logged
  When reconcile runs since 2026-10-31
  Then the missed turn is filled and reported under its day
  And the approximate turn gets its exact wall clock
  And an unfinished turn is filled with no wall clock
  And a second run adds nothing

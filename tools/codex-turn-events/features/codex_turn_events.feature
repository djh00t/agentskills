Feature: Codex turn events
  Codex pushes turn_complete and needs_approval to a webhook so the Chief of Staff
  does not have to poll. Webhook URL and key never touch disk or logs.

Scenario: Stop posts a minimal turn_complete with a stable event_id
  When the Stop hook runs, and runs again for the same turn with stop_hook_active true
  Then both POSTs carry event_id "codex:{session_id}:{turn_id}:turn_complete" and stop_hook_active
  And the body has only source, event, event_id, session_id, turn_id, task, model, status, pr_url, stop_hook_active, ts
  And no assistant text, summary or cwd is sent

Scenario: PermissionRequest posts needs_approval and starts the human-wait clock
  When the PermissionRequest hook runs twice for the same request
  Then needs_approval is POSTed with tool_name, wait_started_at and the same event_id both times
  And no description, cwd or tool input is sent

Scenario: A redirect is refused and the key never follows it
  Given the webhook answers 302 with a Location on another host
  When the Stop hook runs
  Then the other host receives nothing and the delivery is recorded as posted false, status 302

Scenario: The webhook URL must be https, or http only for localhost
  Given a plain http URL on a non-local host
  When the Stop hook runs
  Then nothing is sent and the delivery records post_error "invalid_url" without the URL

Scenario: A hook never fails the Codex turn
  Given an unreachable webhook or a malformed payload
  When the Stop hook runs
  Then it prints {} and records the failure without the URL
  And the state dir is 0700 and its files are 0600

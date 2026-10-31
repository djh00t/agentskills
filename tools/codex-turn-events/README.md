# codex-turn-events

A small Codex plugin that pushes turn events instead of waiting to be polled. It only
sends events; it does not parse rollouts or keep a turn ledger.

| Hook | Event | Body |
| ---- | ----- | ---- |
| `Stop` (async) | `turn_complete` | `source, event, event_id, session_id, turn_id, task, model, status, pr_url, stop_hook_active, ts` |
| `PermissionRequest` (async) | `needs_approval` | `source, event, event_id, session_id, turn_id, task, model, tool_name, status, wait_started_at, ts` |

`task` is the basename of the turn's `cwd`; `pr_url` is the last GitHub PR URL in the
final assistant message. No assistant text, summary, full `cwd`, tool input or tool
description is sent.

Tokens, cost and wall clock come from [`tools/turn-cost-ledger`](../turn-cost-ledger/),
the one Codex rollout parser. Join its rows to these events on `(session_id, turn_id)`.
Its `--since-last-run` mode is the daily reconcile for turns these hooks miss.

## Dedupe: `event_id`

- `turn_complete`: `codex:{session_id}:{turn_id}:turn_complete`. Stop can fire more than
  once per turn (a Stop hook that continues the turn fires Stop again with
  `stop_hook_active: true`). Every one shares the same `event_id`; the receiver upserts
  on it and keeps the row with the latest `ts` as the turn end.
- `needs_approval`: `codex:{session_id}:{turn_id}:needs_approval:{hash}`, where `hash` is
  the first 16 hex chars of SHA-256 over the tool name and tool input. Codex gives
  PermissionRequest no `tool_use_id`, so a re-delivered request gets the same id while
  two different requests in one turn get different ids. Only the hash leaves the machine.

## Human-wait clock

- **Starts** at `wait_started_at` on `needs_approval`: the UTC time the hook process ran.
  Hooks are async (Codex runs up to 8 at a time per session), so this can lag the
  prompt the human saw by however long the hook waited in the queue. The payload has
  no Codex-side timestamp to use instead.
- **Ends** at the `ts` of the next event for the same `session_id`, either the next
  `needs_approval` or the `turn_complete`. Codex has no hook for "approval answered",
  so this is an upper bound: it includes the approved tool's run time and any work after
  it in the same turn. A `needs_approval` with no later event stays open.

## Delivery

Hooks always print `{}` and exit 0 (hook `timeout` is 30 s), so they never break a turn.

- The URL must be `https://`; `http://` is allowed only for `localhost` and `127.0.0.1`.
  Anything else is not sent and is recorded as `post_error: "invalid_url"`.
- Redirects are refused. A 3xx is a failure (`posted: false`, `post_status: 3xx`), so
  the key is never re-sent to a `Location` host.
- Errors record the status code or exception class only, never the URL or key.

## Webhook URL and key

Read at run time, never logged, printed or written to disk:

1. Env vars `CODEX_EVENTS_WEBHOOK_URL` and `CODEX_EVENTS_WEBHOOK_KEY`, else
2. macOS Keychain generic passwords with services `codex-events-webhook-url` and
   `codex-events-webhook-key`.

The key goes in `Authorization: Bearer <key>` unless `CODEX_EVENTS_WEBHOOK_KEY_HEADER`
names another header (then the raw key is sent in that header).

## Files

`~/.local/state/codex-turn-events/` (override with `CODEX_TURN_EVENTS_DIR`), created
`0700` with files `0600`:

- `delivery.jsonl`: one row per send (`event_id, event, ts, posted, post_status|post_error`).
- `hook-errors.jsonl`: hook failures (error class only).

## Install

Not installed by this repo. After merge, add the plugin to the local Codex marketplace,
then trust its hooks with `/hooks`.

## Checks

```shell
make check
```

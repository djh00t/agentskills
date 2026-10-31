# codex-turn-events

A small Codex plugin that pushes turn events instead of waiting to be polled.

| Hook | What it does |
| ---- | ------------ |
| `Stop` (async) | Reads that turn from `transcript_path`, appends a row to `turns.jsonl` (model, input, cache-read, cache-write, output, reasoning tokens, wall clock), then POSTs `turn_complete` with session, task, status, PR URL, tokens and wall clock. |
| `PermissionRequest` (async) | Appends and POSTs `needs_approval` with the tool name and description. Its `wait_started_at` starts the human-wait clock. |

Codex hook payloads carry no token usage, so the Stop hook reads the rollout. When the
Stop hook fires before `task_complete` is written, wall clock is approximate
(`now - task_started.started_at`, `wall_clock_exact=false`); the daily reconcile replaces it.

Hooks always print `{}` and exit 0, so they never break a turn. Failures go to
`hook-errors.jsonl` (error class only).

## Webhook URL and key

Read at run time, never logged, printed or written to disk:

1. Env vars `CODEX_EVENTS_WEBHOOK_URL` and `CODEX_EVENTS_WEBHOOK_KEY`, else
2. macOS Keychain generic passwords with services `codex-events-webhook-url` and
   `codex-events-webhook-key`.

The key goes in `Authorization: Bearer <key>` unless `CODEX_EVENTS_WEBHOOK_KEY_HEADER`
names another header (then the raw key is sent in that header). With no URL the
event is still logged locally with `posted=false`.

## Files

`~/.local/state/codex-turn-events/` (override with `CODEX_TURN_EVENTS_DIR`):
`turns.jsonl`, `events.jsonl`, `hook-errors.jsonl`, `reconcile-state.json`.
Readers take the last row per `(session_id, turn_id)` in `turns.jsonl`.

## Daily reconcile

```shell
python3 codex_turn_events.py reconcile               # since the day before the last run
python3 codex_turn_events.py reconcile --since 2026-10-24
```

Re-scans `~/.codex/sessions`, appends rows for turns the hooks missed
(`source=reconcile`), upgrades approximate wall clocks, and prints a JSON gap report
(`filled_missing`, `upgraded_wall_clock`, `missing_by_day`). It never POSTs.

`make launchd-plist` renders `build/com.djh00t.codex-turn-events.reconcile.plist`
(daily 07:47). Loading it is a manual step:
`cp build/*.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.djh00t.codex-turn-events.reconcile.plist`.

## Install

Not installed by this repo. After merge, add the plugin to the local Codex marketplace,
then trust its hooks with `/hooks`.

## Checks

```shell
make check
```

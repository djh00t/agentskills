# turn-cost-ledger

Per-turn cost and wall-clock ledger for Codex CLI, built on data that already exists.

- **Tokens and model**: Codex rollouts in `~/.codex/sessions/**/*.jsonl`
  (`turn_context.model`, one `token_usage_record` per model call).
- **Wall clock**: `event_msg/task_complete.duration_ms` and `time_to_first_token_ms`.
- **Cost**: joined from the fsm-ledger files
  (`~/.agents/status-matrices/*/usage.jsonl`) on the `event_id` the Codex hook writes,
  `codex:{session_id}:{response_id}`. This tool does not re-price anything. Per row:
  1. a numeric `api_equivalent_usd` is used when present (subscription rows from the
     fsm-ledger billing code);
  2. otherwise a `cost_is_plan` row (`billing_mode=subscription`, `costTotal=0`) is
     **unpriced**: the 0 is the plan's marginal cost, not the API rate, so it is never
     counted as $0;
  3. otherwise `costTotal`, priced at API rates from the models.dev snapshot.

Bad token counts count as 0, and a call whose `usage` is not an object is skipped.
A call the fsm-ledger has not priced yet is counted in `calls_unpriced`, and the turn
gets `cost_complete=false`. Nothing is guessed.

## Usage

```shell
python3 turn_cost_ledger.py                    # CSV of every turn to stdout
python3 turn_cost_ledger.py --since 2026-10-31 --format jsonl   # by rollout path date
python3 turn_cost_ledger.py --since-last-run > /dev/null   # daily reconcile, gap report on stderr
```

## Daily reconcile

Hooks can fail (Codex not trusting them yet, a webhook down, the fsm-ledger hook
erroring). Rollouts are written by Codex itself, so a daily `--since-last-run` run
rebuilds every turn from them and reports what is still missing:

- Scans every rollout whose file was modified (mtime) on or after the day before the
  last run (all of them on the first run). It uses mtime, not the `YYYY/MM/DD` path
  date, because a resumed session appends its new turns to the original, older-dated
  rollout file. The one-day overlap catches turns that finished after the previous run.
- Prints the usual ledger on stdout. Because of the overlap, consecutive runs repeat
  some turns: anyone keeping the output must dedupe on `(session_id, turn_id)`, keeping
  the **last** row (a later run sees the finished turn).
- Writes one JSON gap report to stderr: `since`, `turns`, `cost_incomplete`,
  `no_wall_clock` and `by_day`.
- Records today's date in `--state` (default
  `~/.local/state/turn-cost-ledger/last-run.json`, dir `0700`, file `0600`).

Example launchd job (not installed by this repo). Save as
`~/Library/LaunchAgents/com.example.turn-cost-ledger.plist`, replace the paths, then
`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.turn-cost-ledger.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.example.turn-cost-ledger</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/agentskills/tools/turn-cost-ledger/turn_cost_ledger.py</string>
    <string>--since-last-run</string>
    <string>--format</string><string>jsonl</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/usr/bin:/bin</string>
    <key>PYTHONDONTWRITEBYTECODE</key><string>1</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>47</integer></dict>
  <!-- stdout is the full ledger and overlaps the previous run by a day, so appending it
       to a log double-counts. The gap report on stderr is what this job is for. -->
  <key>StandardOutPath</key><string>/dev/null</string>
  <key>StandardErrorPath</key><string>/path/to/logs/turn-cost-ledger.gaps.log</string>
</dict>
</plist>
```

launchd does not expand `~` or `$HOME` in these paths, so use absolute paths. To keep
the ledger itself, write each run to its own file (not an appended log) and dedupe on
`(session_id, turn_id)`, keeping the last row.

Turn events from `tools/codex-turn-events` join to these rows on `(session_id, turn_id)`.

## Columns

`started_at, session_id, turn_id, cwd, model, calls, input_tokens, cache_read_tokens,
cache_write_tokens, output_tokens, reasoning_tokens, wall_clock_s, ttft_s,
est_cost_usd, calls_unpriced, cost_complete, pricing_date, pricing_source`

`input_tokens` includes cached tokens (OpenAI convention). `output_tokens` includes
reasoning tokens.

## Checks

```shell
make check
```

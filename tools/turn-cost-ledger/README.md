# turn-cost-ledger

Per-turn cost and wall-clock ledger for Codex CLI, built on data that already exists.

- **Tokens and model**: Codex rollouts in `~/.codex/sessions/**/*.jsonl`
  (`turn_context.model`, one `token_usage_record` per model call).
- **Wall clock**: `event_msg/task_complete.duration_ms` and `time_to_first_token_ms`.
- **Cost**: joined by `response_id` from the fsm-ledger files
  (`~/.agents/status-matrices/*/usage.jsonl`), which price each call from the
  models.dev snapshot. Subscription-billed calls use `api_equivalent_usd` (API rates),
  never the plan amount. This tool does not re-price anything.

A call the fsm-ledger has not priced yet is counted in `calls_unpriced`, and the turn
gets `cost_complete=false`. Nothing is guessed.

## Usage

```shell
python3 turn_cost_ledger.py                    # CSV of every turn to stdout
python3 turn_cost_ledger.py --since 2026/10/31 --format jsonl
```

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

Workflow: DailyPortfolioAlphaWorkflow (deterministic)

Inputs (contracts v1):

- portfolio_input.json
- watchlist_input.json
- market_context.json
- policy.json
- data_source_config (yahoo adapter, interval, lookback days)

Activities (all deterministic given identical inputs + identical market data snapshot):

1) ValidateInputsActivity
   - validates JSON schemas + pydantic models

2) FetchMarketDataActivity
   - fetches OHLCV for all symbols (or reads from cache)
   - persists a "market_data_snapshot_id" (content hash) for reproducibility

3) ComputeRecommendationsActivity
   - computes indicators + scores + stops + tax notes + actions
   - outputs DailyBrief JSON

4) RenderReportActivity
   - renders deterministic markdown report

5) PersistOutputsActivity
   - stores outputs in local folder or S3-compatible store (optional)
   - writes an audit manifest:
     - inputs hashes
     - policy version
     - code version
     - market_data_snapshot_id

Scheduling:

- Run once daily (external cron/k8s) and start workflow with that date.
- Backfills supported by providing historical inputs + market snapshot.

Determinism:

- No random numbers.
- All rounding and thresholds are policy-configured.
- Output must be stable for the same inputs + same market snapshot.

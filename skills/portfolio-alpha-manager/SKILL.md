---
name: portfolio-alpha-manager
description: Deterministic portfolio alpha workflow with constraints, lot selection, fee models, and correlation clusters.
compatibility: agents
metadata:
  language: python
  scope: portfolio-optimization
---
# PORTFOLIO_ALPHA_MANAGER

## Purpose

Deterministic daily portfolio skill for:

- holdings recommendations (`ACCUMULATE`, `BUY`, `HOLD`, `TRIM`, `SELL`)
- watchlist opportunity ranking
- portfolio-level target weight optimization under constraints
- correlation-cluster construction from rolling returns (`CL_00`, `CL_01`, ...)
- deterministic trade plan generation (BUY/SELL quantity + limits + estimated fees)
- tax-lot-aware sell optimization
- audit manifest generation for reproducibility

## Deterministic Guarantees

The skill must produce stable outputs for identical inputs:

- sorted symbol processing
- deterministic ranking and tie-breaks
- deterministic fee estimation
- deterministic lot selection order
- deterministic hierarchical clustering with explicit tie-breakers
- deterministic input and market snapshot hashing

## Required Inputs

- `portfolio.json` (contract: `contracts/v1/portfolio_input.schema.json`)
- `watchlist.json` (contract: `contracts/v1/watchlist_input.schema.json`)
- `market.json` (contract: `contracts/v1/market_context.schema.json`)
- `policy.json` (default: `configs/policy.default.json`)

## Optional Inputs

- `mappings/symbol_map.json`
  - Used to inject `sector` and `cluster` metadata for symbols.
  - If missing metadata, use `UNKNOWN` buckets for exposure checks.

Example:

```json
{
  "AAPL": { "sector": "TECH", "cluster": "MEGA_TECH" },
  "NVDA": { "sector": "TECH", "cluster": "AI_SEMIS" },
  "GLDM": { "sector": "COMMODITIES", "cluster": "GOLD" }
}
```

## Core Policy Controls

- Capital:
  - `capital.max_new_trade_pct`
  - `capital.max_asset_pct`
  - `capital.max_sector_pct`
  - `capital.max_cluster_pct`
- Costs:
  - `costs.fee_model` (`flat`, `ibkr_us_tiered`, `ibkr_au_asx`)
  - `costs.per_trade_fee`
  - `costs.slippage_bps`
- Risk:
  - `risk.portfolio_heat_defensive`
- Tax:
  - `tax.au_long_term_days`
  - `tax.lot_selection_method` (`FIFO`, `LIFO`, `MIN_TAX`, `HARVEST_LOSS`, `MIN_GAIN`, `MAX_GAIN`)
- Correlation Clusters:
  - `correlation_clusters.enabled`
  - `correlation_clusters.window_days`
  - `correlation_clusters.min_overlap_days`
  - `correlation_clusters.cluster_cut.mode`
  - `correlation_clusters.cluster_cut.distance_threshold`
  - `correlation_clusters.max_clusters`

## Execution Workflow

1. Validate input contracts.
2. Load portfolio/watchlist/market/policy.
3. Load optional symbol map and enrich holdings/watchlist diagnostics.
4. Fetch OHLCV market data with deterministic cache keying.
5. Build deterministic correlation clusters if symbols are missing cluster metadata.
6. Generate per-symbol recommendations.
7. Compute portfolio heat and defensive mode flag.
8. Build constraint-aware target weights.
9. Build deterministic orders:
   - SELL/TRIM orders with tax-lot selection
   - BUY/ACCUMULATE orders bounded by remaining cash
10. Build audit manifest:
   - input file hashes
   - code version
   - policy version
   - market snapshot id
   - cluster builder provenance and `cluster_map_hash`
11. Write output artifacts.

## Outputs

- `daily_brief.json` (contract: `contracts/v1/daily_brief.schema.json`)
  - includes `recommendations`
  - includes `watchlist_opportunities`
  - includes `trade_plan.target_weights`
  - includes `trade_plan.orders`
  - includes `audit`
- `daily_brief.md` (human-readable summary)
- `audit_manifest.json` (same audit object persisted separately)
- `clusters.json` (optional deterministic cluster map output)

## CLI Usage

```bash
# OpenClaw docker runtime bootstrap (if pip/deps are missing)
make bootstrap-openclaw

python -m pam.cli daily \
  --portfolio portfolio.json \
  --watchlist watchlist.json \
  --market market.json \
  --policy configs/policy.default.json \
  --symbol-map mappings/symbol_map.json \
  --out-json daily_brief.json \
  --out-md daily_brief.md \
  --out-audit audit_manifest.json \
  --out-clusters clusters.json

python -m pam.cli clusters build \
  --symbols AAPL --symbols MSFT --symbols NVDA \
  --as-of 2026-02-15 \
  --policy configs/policy.default.json \
  --out clusters.json
```

## Safety and Behavior Rules

- Preserve capital before return maximization.
- Keep explicit stop logic in recommendations.
- Do not bypass sector or cluster exposure caps.
- Do not exceed deterministic sizing and cash checks.
- Keep tax and fee impacts explicit in outputs.
- Avoid adding non-deterministic data sources or randomization.

## Agent Instructions

When invoked:

1. Analyze existing holdings first.
2. Identify concentration and exposure risks.
3. Rank watchlist opportunities by deterministic scores.
4. Produce explicit entry/exit and stop logic.
5. Apply policy constraints to target weights.
6. Build a deterministic trade plan with fee estimates.
7. Use lot selection policy for all sell-side quantity.
8. Emit audit metadata for reproducibility.
9. Return concise risk alerts and implementation notes.

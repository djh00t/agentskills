OpenClaw docker bootstrap (no pip/uv preinstalled):
  make bootstrap-openclaw

Install (local dev):
  python -m pip install -e ".[test]"

Daily run (local):
  python -m pam.cli daily --portfolio portfolio.json --watchlist watchlist.json --market market.json \
    --symbol-map mappings/symbol_map.json --out-audit audit_manifest.json \
    --out-clusters clusters.json

Correlation clusters (deterministic):
  python -m pam.cli clusters build --symbols AAPL --symbols MSFT --symbols NVDA \
    --as-of 2026-02-15 --out clusters.json

Quality gates:
  make install
  make check

Outputs:
  daily_brief.json  (contracts/v1/daily_brief.schema.json)
  daily_brief.md
  audit_manifest.json
  clusters.json (optional)

Temporal Worker:
  export TEMPORAL_ADDRESS=localhost:7233
  export PAM_TASK_QUEUE=pam-daily
  pam-worker

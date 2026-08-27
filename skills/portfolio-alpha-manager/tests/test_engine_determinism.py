from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
from pam.config import Policy
from pam.engine import EngineInputs, recommend_for_symbol
from pam.models import Holding


def _sample_df() -> pd.DataFrame:
    # deterministic synthetic OHLCV (no randomness)
    idx = pd.date_range("2024-01-01", periods=260, freq="D", tz="UTC")
    close = pd.Series([100 + (i * 0.05) for i in range(len(idx))], index=idx)
    high = close * 1.01
    low = close * 0.99
    open_ = close
    vol = pd.Series([1_000_000 for _ in range(len(idx))], index=idx)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol})


def test_recommendation_is_stable(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "capital": {
                    "max_new_trade_pct": 0.01,
                    "max_asset_pct": 0.05,
                    "max_sector_pct": 0.2,
                    "max_cluster_pct": 0.3,
                },
                "costs": {"per_trade_fee": 1.0, "slippage_bps": 5},
                "risk": {
                    "portfolio_heat_defensive": 0.75,
                    "portfolio_heat_reduce": 0.85,
                    "risk_per_trade_pct": 0.005,
                    "min_reward_risk": 2.0,
                },
                "trend": {
                    "ma_fast": 20,
                    "ma_mid": 50,
                    "ma_slow": 200,
                    "adx_period": 14,
                    "rsi_period": 14,
                },
                "stops": {
                    "atr_period": 14,
                    "atr_trailing_mult": 2.0,
                    "fallback_trailing_pct_low_vol": 0.08,
                    "fallback_trailing_pct_high_vol": 0.06,
                    "high_vol_atr_pct_threshold": 0.04,
                },
                "signals": {
                    "buy_trend_score_min": 0.60,
                    "buy_momentum_score_min": 0.55,
                    "sell_breakdown_score_min": 0.60,
                    "trim_extension_atr": 2.0,
                    "rsi_overbought": 75,
                    "rsi_pullback_low": 40,
                    "rsi_pullback_high": 55,
                },
                "tax": {
                    "au_long_term_days": 365,
                    "us_long_term_days": 365,
                    "prefer_hold_to_long_term_days_remaining": 45,
                },
                "rounding": {"price_decimals": 4, "pct_decimals": 4},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    pol = Policy.load(policy_path)
    eng_in = EngineInputs(
        policy=pol,
        as_of=date(2026, 2, 15),
        base_currency="AUD",
        cash_available=10000,
        margin_available=0,
    )
    df = _sample_df()

    holding = Holding(symbol="TEST", quantity=10, avg_price=100, purchase_date=date(2025, 1, 1))
    r1 = recommend_for_symbol("TEST", df, holding, eng_in, "RISK_ON")
    r2 = recommend_for_symbol("TEST", df, holding, eng_in, "RISK_ON")

    assert r1.model_dump() == r2.model_dump()

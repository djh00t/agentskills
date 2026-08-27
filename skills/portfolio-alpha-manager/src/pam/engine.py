from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Tuple, cast

import pandas as pd
from pam.config import Policy
from pam.fees import FeeConfig, Model, estimate_execution_cost
from pam.models import Holding, Recommendation
from pam.risk import compute_stops
from pam.scoring import compute_scores
from pam.tax import holding_period_note


@dataclass(frozen=True)
class EngineInputs:
    policy: Policy
    as_of: date
    base_currency: str
    cash_available: float
    margin_available: float


def _round_pair(a: float, b: float, d: int) -> Tuple[float, float]:
    lo = round(min(a, b), d)
    hi = round(max(a, b), d)
    return (lo, hi)


def _confidence(trend: float, momentum: float, breakdown: float) -> float:
    # deterministic confidence: rewards alignment, penalizes breakdown
    c = 0.55 * trend + 0.45 * momentum - 0.40 * breakdown
    return float(max(0.0, min(1.0, c)))


def _fee_cfg(policy: Policy) -> FeeConfig:
    fee_model = str(policy.get("costs", "fee_model", default="flat"))
    if fee_model not in {"flat", "ibkr_us_tiered", "ibkr_au_asx"}:
        fee_model = "flat"
    fee = float(policy.get("costs", "per_trade_fee", default=1.0))
    slip = float(policy.get("costs", "slippage_bps", default=5))
    return FeeConfig(model=cast(Model, fee_model), flat_fee=fee, slippage_bps=slip)


def recommend_for_symbol(
    sym: str,
    df: pd.DataFrame,
    holding: Holding | None,
    engine_in: EngineInputs,
    market_regime: str,
) -> Recommendation:
    pol = engine_in.policy
    price_d = int(pol.get("rounding", "price_decimals", default=4))
    pct_d = int(pol.get("rounding", "pct_decimals", default=4))

    scores = compute_scores(
        df=df,
        ma_fast=int(pol.get("trend", "ma_fast")),
        ma_mid=int(pol.get("trend", "ma_mid")),
        ma_slow=int(pol.get("trend", "ma_slow")),
        rsi_p=int(pol.get("trend", "rsi_period")),
        adx_p=int(pol.get("trend", "adx_period")),
        atr_p=int(pol.get("stops", "atr_period")),
    )
    stops = compute_stops(
        df=df,
        atr_period=int(pol.get("stops", "atr_period")),
        atr_trailing_mult=float(pol.get("stops", "atr_trailing_mult")),
        high_vol_atr_pct_threshold=float(pol.get("stops", "high_vol_atr_pct_threshold")),
        fallback_trailing_low_vol_pct=float(pol.get("stops", "fallback_trailing_pct_low_vol")),
        fallback_trailing_high_vol_pct=float(pol.get("stops", "fallback_trailing_pct_high_vol")),
        price_decimals=price_d,
    )

    # Entry/exit zones: deterministic bands around MA20/MA50 with ATR guidance.
    entry_center = scores.ma20 if scores.trend >= 0.5 else scores.ma50
    entry_lo, entry_hi = _round_pair(entry_center * 0.985, entry_center * 1.005, price_d)

    # Target: 2R based on distance to hard stop from current price / entry_center.
    risk_per_share = max(0.0001, (scores.price - stops.hard_stop))
    target = scores.price + 2.0 * risk_per_share
    exit_lo, exit_hi = _round_pair(target * 0.99, target * 1.02, price_d)

    rr = (target - scores.price) / risk_per_share if risk_per_share > 0 else 0.0
    rr = round(float(rr), 4)

    conf = round(_confidence(scores.trend, scores.momentum, scores.breakdown), 4)

    buy_trend_min = float(pol.get("signals", "buy_trend_score_min"))
    buy_mom_min = float(pol.get("signals", "buy_momentum_score_min"))
    sell_break_min = float(pol.get("signals", "sell_breakdown_score_min"))

    # Deterministic action logic with regime overlay.
    action = "HOLD"
    if scores.breakdown >= sell_break_min:
        action = "SELL" if holding is not None else "HOLD"
    else:
        if scores.trend >= buy_trend_min and scores.momentum >= buy_mom_min:
            action = "ACCUMULATE" if holding is not None else "BUY"
        # Trim if extended and you already hold
        trim_ext_atr = float(pol.get("signals", "trim_extension_atr"))
        if (
            holding is not None
            and scores.atr_pct > 0
            and (scores.price - scores.ma20) / scores.price >= (trim_ext_atr * scores.atr_pct)
        ):
            action = "TRIM"

    # RISK_OFF tightens bias: avoid buys unless very strong
    if market_regime == "RISK_OFF" and action in ("BUY", "ACCUMULATE"):
        if not (scores.trend >= 0.8 and scores.momentum >= 0.7):
            action = "HOLD" if holding is not None else "HOLD"

    # Position sizing: deterministic cap.
    max_new_trade = float(pol.get("capital", "max_new_trade_pct"))
    pos_size = max_new_trade if action in ("BUY", "ACCUMULATE") else 0.0
    pos_size = round(pos_size, pct_d)

    # Tax note if holding exists.
    tax_note = "N/A"
    if holding is not None:
        long_term_days = int(pol.get("tax", "au_long_term_days"))
        prefer_hold = int(pol.get("tax", "prefer_hold_to_long_term_days_remaining"))
        tn = holding_period_note(
            holding.purchase_date, engine_in.as_of, long_term_days, prefer_hold
        )
        tax_note = tn.note

    fee_cfg = _fee_cfg(pol)
    est_fee = estimate_execution_cost(fee_cfg, notional=scores.price * 1.0, shares=1.0)
    fees_note = (
        f"Fee model={fee_cfg.model}, est per-share exec={round(est_fee, 4)} (incl slippage)."
    )

    return Recommendation(
        symbol=sym,
        action=action,  # type: ignore
        confidence=conf,
        entry_range=(entry_lo, entry_hi),
        exit_range=(exit_lo, exit_hi),
        hard_stop=stops.hard_stop,
        trailing_stop=stops.trailing_desc,
        position_size_pct=pos_size,
        reward_risk_ratio=rr,
        tax_note=tax_note,
        fees_note=fees_note,
        diagnostics={
            "trend_score": round(scores.trend, 4),
            "momentum_score": round(scores.momentum, 4),
            "breakdown_score": round(scores.breakdown, 4),
            "rsi": round(scores.rsi, 2),
            "adx": round(scores.adx, 2),
            "atr_pct": round(scores.atr_pct, 6),
            "price": round(scores.price, 4),
            "ma20": round(scores.ma20, 4),
            "ma50": round(scores.ma50, 4),
            "ma200": round(scores.ma200, 4),
            "sector": holding.sector if holding is not None else None,
            "cluster": holding.cluster if holding is not None else None,
        },
    )

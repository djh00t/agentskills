from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from pam.indicators import atr


@dataclass(frozen=True)
class Stops:
    hard_stop: float
    trailing_desc: str


def compute_stops(
    df: pd.DataFrame,
    atr_period: int,
    atr_trailing_mult: float,
    high_vol_atr_pct_threshold: float,
    fallback_trailing_low_vol_pct: float,
    fallback_trailing_high_vol_pct: float,
    price_decimals: int,
) -> Stops:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    at = atr(high, low, close, atr_period)
    last_price = float(close.iloc[-1])
    atr_val = float(at.iloc[-1]) if pd.notna(at.iloc[-1]) else 0.0
    atr_pct = (atr_val / last_price) if last_price > 0 else 0.0

    # Hard stop = last_price - 2*ATR (guardrail); this is a default for new entries.
    hard_stop = round(last_price - (2.0 * atr_val), price_decimals)

    # Trailing: highest close - mult*ATR (if ATR valid), otherwise fixed pct
    highest_close_20 = float(close.tail(20).max())
    if atr_val > 0:
        trail_level = highest_close_20 - atr_trailing_mult * atr_val
        trail_level = round(trail_level, price_decimals)
        trailing_desc = f"{trail_level} (highest_close_20 - {atr_trailing_mult}*ATR)"
    else:
        pct = (
            fallback_trailing_high_vol_pct
            if atr_pct >= high_vol_atr_pct_threshold
            else fallback_trailing_low_vol_pct
        )
        trailing_desc = f"{round(pct * 100, 2)}% from recent high (fallback)"

    return Stops(hard_stop=hard_stop, trailing_desc=trailing_desc)

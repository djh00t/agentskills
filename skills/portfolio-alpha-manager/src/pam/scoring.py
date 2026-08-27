from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pam.indicators import adx, atr, rsi, sma


@dataclass(frozen=True)
class Scores:
    trend: float
    momentum: float
    breakdown: float
    atr_pct: float
    rsi: float
    adx: float
    price: float
    ma20: float
    ma50: float
    ma200: float


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def compute_scores(
    df: pd.DataFrame,
    ma_fast: int,
    ma_mid: int,
    ma_slow: int,
    rsi_p: int,
    adx_p: int,
    atr_p: int,
) -> Scores:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ma20 = sma(close, ma_fast)
    ma50 = sma(close, ma_mid)
    ma200 = sma(close, ma_slow)

    r = rsi(close, rsi_p)
    a = adx(high, low, close, adx_p)
    at = atr(high, low, close, atr_p)

    last = close.index[-1]
    price = float(close.loc[last])
    ma20v = float(ma20.loc[last])
    ma50v = float(ma50.loc[last])
    ma200v = float(ma200.loc[last])
    rsiv = float(r.loc[last]) if not np.isnan(r.loc[last]) else 50.0
    adxv = float(a.loc[last]) if not np.isnan(a.loc[last]) else 10.0
    atrv = float(at.loc[last]) if not np.isnan(at.loc[last]) else 0.0
    atr_pct = float(atrv / price) if price > 0 else 0.0

    # Trend: MA alignment + price above key MAs
    align = 1.0 if (ma20v > ma50v > ma200v) else 0.0
    above = (1.0 if price > ma50v else 0.0) * 0.6 + (1.0 if price > ma200v else 0.0) * 0.4
    trend = _clip01(0.55 * align + 0.45 * above)

    # Momentum: RSI mid-zone is best; penalize extremes. ADX indicates trend strength.
    rsi_score = 1.0 - (abs(rsiv - 55.0) / 55.0)
    rsi_score = _clip01(rsi_score)
    adx_score = _clip01((adxv - 10.0) / 30.0)  # 10..40 mapped
    momentum = _clip01(0.65 * rsi_score + 0.35 * adx_score)

    # Breakdown: price below MA50 and MA200 and MA slopes negative
    ma50_slope = (
        float((ma50.iloc[-1] - ma50.iloc[-6]) / ma50.iloc[-6])
        if len(ma50) >= 6 and ma50.iloc[-6]
        else 0.0
    )
    ma200_slope = (
        float((ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6])
        if len(ma200) >= 6 and ma200.iloc[-6]
        else 0.0
    )
    below = (1.0 if price < ma50v else 0.0) * 0.6 + (1.0 if price < ma200v else 0.0) * 0.4
    slope_bad = _clip01((-(ma50_slope + ma200_slope)) * 10.0)  # scale
    breakdown = _clip01(0.65 * below + 0.35 * slope_bad)

    return Scores(
        trend=trend,
        momentum=momentum,
        breakdown=breakdown,
        atr_pct=atr_pct,
        rsi=rsiv,
        adx=adxv,
        price=price,
        ma20=ma20v,
        ma50=ma50v,
        ma200=ma200v,
    )

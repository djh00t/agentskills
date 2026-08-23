from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Model = Literal["flat", "ibkr_us_tiered", "ibkr_au_asx"]


@dataclass(frozen=True)
class FeeConfig:
    model: Model
    flat_fee: float
    slippage_bps: float


def estimate_execution_cost(cfg: FeeConfig, notional: float, shares: float) -> float:
    slip = (cfg.slippage_bps / 10000.0) * notional

    if cfg.model == "flat":
        return cfg.flat_fee + slip

    if cfg.model == "ibkr_us_tiered":
        per_share = 0.0035 * max(0.0, shares)
        fee = max(0.35, per_share)
        fee = min(fee, 0.01 * notional)
        return fee + slip

    if cfg.model == "ibkr_au_asx":
        fee = max(5.0, 0.0008 * notional)
        fee = min(fee, 75.0)
        return fee + slip

    return cfg.flat_fee + slip

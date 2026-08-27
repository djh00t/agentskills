from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from pam.models import Recommendation


@dataclass(frozen=True)
class Constraints:
    max_asset_pct: float
    max_sector_pct: float
    max_cluster_pct: float
    max_new_trade_pct: float


def _sym_sector(rec: Recommendation) -> str:
    return str(rec.diagnostics.get("sector") or "UNKNOWN")


def _sym_cluster(rec: Recommendation) -> str:
    return str(rec.diagnostics.get("cluster") or "UNKNOWN")


def build_target_weights(
    holdings_recs: List[Recommendation],
    watchlist_recs: List[Recommendation],
    constraints: Constraints,
    defensive: bool,
) -> Dict[str, float]:
    universe = holdings_recs + watchlist_recs
    ranked = sorted(
        universe,
        key=lambda rec: (
            rec.confidence,
            rec.reward_risk_ratio,
            float(rec.diagnostics.get("trend_score", 0.0)),
        ),
        reverse=True,
    )

    target: Dict[str, float] = {}
    sector_w: Dict[str, float] = {}
    cluster_w: Dict[str, float] = {}
    risk_budget = 0.60 if defensive else 0.85

    for rec in ranked:
        if rec.action not in ("BUY", "ACCUMULATE", "HOLD"):
            continue

        sym = rec.symbol
        if sym in target:
            continue

        sector = _sym_sector(rec)
        cluster = _sym_cluster(rec)
        add = min(
            constraints.max_asset_pct,
            (
                constraints.max_new_trade_pct
                if rec.action in ("BUY", "ACCUMULATE")
                else constraints.max_asset_pct
            ),
        )

        if sector_w.get(sector, 0.0) + add > constraints.max_sector_pct:
            continue
        if cluster_w.get(cluster, 0.0) + add > constraints.max_cluster_pct:
            continue

        target[sym] = add
        sector_w[sector] = sector_w.get(sector, 0.0) + add
        cluster_w[cluster] = cluster_w.get(cluster, 0.0) + add

        if sum(target.values()) >= risk_budget:
            break

    total = sum(target.values())
    if total > risk_budget and total > 0:
        scale = risk_budget / total
        for sym in list(target.keys()):
            target[sym] = round(target[sym] * scale, 6)
    return target

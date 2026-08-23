from __future__ import annotations

from pam.models import Recommendation
from pam.optimizer import Constraints, build_target_weights


def _rec(sym: str, conf: float, sector: str, cluster: str) -> Recommendation:
    return Recommendation(
        symbol=sym,
        action="BUY",
        confidence=conf,
        entry_range=(1.0, 1.0),
        exit_range=(2.0, 2.0),
        hard_stop=0.9,
        trailing_stop="x",
        position_size_pct=0.01,
        reward_risk_ratio=2.0,
        tax_note="N/A",
        fees_note="N/A",
        diagnostics={"sector": sector, "cluster": cluster, "trend_score": 0.9},
    )


def test_sector_cap_enforced() -> None:
    cons = Constraints(
        max_asset_pct=0.05,
        max_sector_pct=0.06,
        max_cluster_pct=0.30,
        max_new_trade_pct=0.05,
    )
    recs = []
    opps = [
        _rec("A", 0.9, "TECH", "X"),
        _rec("B", 0.8, "TECH", "Y"),
        _rec("C", 0.7, "HEALTH", "Z"),
    ]
    tgt = build_target_weights(recs, opps, cons, defensive=False)
    assert sum(v for k, v in tgt.items() if k in ("A", "B")) <= 0.06 + 1e-9

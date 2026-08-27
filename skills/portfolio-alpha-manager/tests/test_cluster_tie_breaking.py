from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from pam.clusters.builder import build_correlation_clusters
from pam.config import Policy


def _policy() -> Policy:
    return Policy(
        raw={
            "version": "v1",
            "correlation_clusters": {
                "enabled": True,
                "returns_type": "close_to_close",
                "returns_method": "log",
                "window_days": 126,
                "min_overlap_days": 90,
                "winsorize_pct": 0.0,
                "nan_policy": "pairwise_drop",
                "corr_method": "pearson",
                "distance": "one_minus_corr",
                "linkage": "average",
                "cluster_cut": {"mode": "max_clusters", "distance_threshold": 0.35},
                "min_cluster_size": 1,
                "max_clusters": 2,
                "label_prefix": "CL",
                "label_width": 2,
            },
        }
    )


def test_equal_distances_use_lexicographic_tie_break() -> None:
    t = np.arange(220)
    shared = 0.001 + 0.0001 * np.sin(t / 4.0)
    ohlcv: dict[str, pd.DataFrame] = {}
    for sym in ["A", "B", "C", "D"]:
        idx = pd.date_range(start="2025-01-01", periods=len(shared), freq="D", tz="UTC")
        close = 100.0 * np.exp(np.cumsum(shared))
        close_s = pd.Series(close, index=idx)
        ohlcv[sym] = pd.DataFrame(
            {
                "Open": close_s,
                "High": close_s,
                "Low": close_s,
                "Close": close_s,
                "Volume": 1_000_000.0,
            }
        )

    out = build_correlation_clusters(
        ohlcv_map=ohlcv,
        symbols=["A", "B", "C", "D"],
        as_of=date(2025, 8, 8),
        policy=_policy(),
        market_snapshot_id="snap-tie",
    )

    assert out.cluster_map["A"] == out.cluster_map["B"]
    assert out.cluster_map["B"] == out.cluster_map["C"]
    assert out.cluster_map["A"] != out.cluster_map["D"]

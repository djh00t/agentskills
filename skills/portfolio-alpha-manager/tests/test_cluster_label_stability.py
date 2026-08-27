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
                "cluster_cut": {"mode": "distance_threshold", "distance_threshold": 0.35},
                "min_cluster_size": 2,
                "max_clusters": 25,
                "label_prefix": "CL",
                "label_width": 2,
            },
        }
    )


def _make_ohlcv(returns: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range(start="2025-01-01", periods=len(returns), freq="D", tz="UTC")
    close = 100.0 * np.exp(np.cumsum(returns))
    close_s = pd.Series(close, index=idx)
    return pd.DataFrame(
        {
            "Open": close_s,
            "High": close_s * 1.001,
            "Low": close_s * 0.999,
            "Close": close_s,
            "Volume": 1_000_000.0,
        }
    )


def test_irrelevant_symbol_does_not_relabel_existing_clusters() -> None:
    t = np.arange(220)
    core = {
        "AAA": _make_ohlcv(0.001 + 0.0002 * np.sin(t / 6.0)),
        "BBB": _make_ohlcv(0.001 + 0.0002 * np.sin(t / 6.0 + 0.1)),
        "CCC": _make_ohlcv(-0.0008 + 0.00015 * np.cos(t / 7.0)),
        "DDD": _make_ohlcv(-0.0008 + 0.00015 * np.cos(t / 7.0 + 0.1)),
    }
    with_extra = dict(core)
    with_extra["ZZZ"] = _make_ohlcv(0.00001 * np.cos(t / 2.0))

    policy = _policy()
    base = build_correlation_clusters(
        ohlcv_map=core,
        symbols=["AAA", "BBB", "CCC", "DDD"],
        as_of=date(2025, 8, 8),
        policy=policy,
        market_snapshot_id="snap-base",
    )
    augmented = build_correlation_clusters(
        ohlcv_map=with_extra,
        symbols=["AAA", "BBB", "CCC", "DDD", "ZZZ"],
        as_of=date(2025, 8, 8),
        policy=policy,
        market_snapshot_id="snap-aug",
    )

    for sym in ["AAA", "BBB", "CCC", "DDD"]:
        assert base.cluster_map[sym] == augmented.cluster_map[sym]

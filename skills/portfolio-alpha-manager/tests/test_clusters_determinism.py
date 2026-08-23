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


def _ohlcv_map(data: dict[str, np.ndarray]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym, ret in data.items():
        idx = pd.date_range(start="2025-01-01", periods=len(ret), freq="D", tz="UTC")
        close = 100.0 * np.exp(np.cumsum(ret))
        close_s = pd.Series(close, index=idx)
        out[sym] = pd.DataFrame(
            {
                "Open": close_s,
                "High": close_s * 1.001,
                "Low": close_s * 0.999,
                "Close": close_s,
                "Volume": 1_000_000.0,
            }
        )
    return out


def test_same_input_twice_is_identical() -> None:
    days = 220
    t = np.arange(days)
    ohlcv = _ohlcv_map(
        {
            "AAA": 0.001 + 0.0002 * np.sin(t / 6.0),
            "BBB": 0.001 + 0.0002 * np.sin(t / 6.0 + 0.1),
            "CCC": -0.0008 + 0.00015 * np.cos(t / 7.0),
            "DDD": -0.0008 + 0.00015 * np.cos(t / 7.0 + 0.1),
        }
    )
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    policy = _policy()
    out1 = build_correlation_clusters(
        ohlcv_map=ohlcv,
        symbols=symbols,
        as_of=date(2025, 8, 8),
        policy=policy,
        market_snapshot_id="snap-001",
    )
    out2 = build_correlation_clusters(
        ohlcv_map=ohlcv,
        symbols=symbols,
        as_of=date(2025, 8, 8),
        policy=policy,
        market_snapshot_id="snap-001",
    )
    assert out1 == out2


def test_reverse_symbol_order_is_identical() -> None:
    days = 220
    t = np.arange(days)
    ohlcv = _ohlcv_map(
        {
            "AAA": 0.001 + 0.0002 * np.sin(t / 6.0),
            "BBB": 0.001 + 0.0002 * np.sin(t / 6.0 + 0.1),
            "CCC": -0.0008 + 0.00015 * np.cos(t / 7.0),
            "DDD": -0.0008 + 0.00015 * np.cos(t / 7.0 + 0.1),
        }
    )
    policy = _policy()
    out1 = build_correlation_clusters(
        ohlcv_map=ohlcv,
        symbols=["AAA", "BBB", "CCC", "DDD"],
        as_of=date(2025, 8, 8),
        policy=policy,
        market_snapshot_id="snap-002",
    )
    out2 = build_correlation_clusters(
        ohlcv_map=ohlcv,
        symbols=["DDD", "CCC", "BBB", "AAA"],
        as_of=date(2025, 8, 8),
        policy=policy,
        market_snapshot_id="snap-002",
    )
    assert out1.cluster_map == out2.cluster_map
    assert out1.cluster_map_hash == out2.cluster_map_hash

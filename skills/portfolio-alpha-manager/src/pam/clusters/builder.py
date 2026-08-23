"""Deterministic correlation-cluster builder for PAM."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Sequence

import numpy as np
import pandas as pd
from pam.clusters.models import (
    ClusterStats,
    CorrelationClusterResult,
    result_from_payload,
    result_to_payload,
)
from pam.config import Policy
from pam.data.cache import Cache


@dataclass(frozen=True)
class ClusterConfig:
    """Policy-derived clustering parameters."""

    returns_type: str
    returns_method: str
    window_days: int
    min_overlap_days: int
    winsorize_pct: float
    nan_policy: str
    corr_method: str
    distance: str
    linkage: str
    cluster_cut_mode: str
    distance_threshold: float
    max_clusters: int
    min_cluster_size: int
    label_prefix: str
    label_width: int
    distance_decimals: int = 6


def _stable_sha256(obj: object) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def config_from_policy(policy: Policy) -> ClusterConfig:
    """Build a normalized cluster config from policy values."""
    section = policy.get("correlation_clusters", default={}) or {}
    cut = section.get("cluster_cut", {}) if isinstance(section, dict) else {}
    return ClusterConfig(
        returns_type=str(section.get("returns_type", "close_to_close")),
        returns_method=str(section.get("returns_method", "log")),
        window_days=int(section.get("window_days", 126)),
        min_overlap_days=int(section.get("min_overlap_days", 90)),
        winsorize_pct=float(section.get("winsorize_pct", 0.0)),
        nan_policy=str(section.get("nan_policy", "pairwise_drop")),
        corr_method=str(section.get("corr_method", "pearson")),
        distance=str(section.get("distance", "one_minus_corr")),
        linkage=str(section.get("linkage", "average")),
        cluster_cut_mode=str(cut.get("mode", "distance_threshold")),
        distance_threshold=float(cut.get("distance_threshold", 0.35)),
        max_clusters=int(section.get("max_clusters", 25)),
        min_cluster_size=int(section.get("min_cluster_size", 2)),
        label_prefix=str(section.get("label_prefix", "CL")),
        label_width=int(section.get("label_width", 2)),
    )


def cache_payload(
    *,
    symbols: Sequence[str],
    as_of: date,
    policy: Policy,
    market_snapshot_id: str,
) -> dict[str, object]:
    """Return a deterministic cache payload for cluster computation."""
    cfg = config_from_policy(policy)
    return {
        "symbols": sorted(set(symbols)),
        "as_of": str(as_of),
        "market_snapshot_id": market_snapshot_id,
        "policy_version": str(policy.get("version")),
        "returns_type": cfg.returns_type,
        "returns_method": cfg.returns_method,
        "window_days": cfg.window_days,
        "min_overlap_days": cfg.min_overlap_days,
        "winsorize_pct": cfg.winsorize_pct,
        "nan_policy": cfg.nan_policy,
        "corr_method": cfg.corr_method,
        "distance": cfg.distance,
        "linkage": cfg.linkage,
        "cluster_cut_mode": cfg.cluster_cut_mode,
        "distance_threshold": cfg.distance_threshold,
        "max_clusters": cfg.max_clusters,
        "min_cluster_size": cfg.min_cluster_size,
        "label_prefix": cfg.label_prefix,
        "label_width": cfg.label_width,
    }


def build_correlation_clusters(
    ohlcv_map: dict[str, pd.DataFrame],
    symbols: list[str],
    as_of: date,
    policy: Policy,
    market_snapshot_id: str,
) -> CorrelationClusterResult:
    """Build deterministic correlation clusters from OHLCV frames."""
    if not isinstance(market_snapshot_id, str):
        raise TypeError("market_snapshot_id must be a string")

    ordered_symbols = sorted(set(symbols))
    cfg = config_from_policy(policy)
    returns = _build_returns(
        ohlcv_map=ohlcv_map,
        symbols=ordered_symbols,
        as_of=as_of,
        cfg=cfg,
    )
    corr = _build_corr_matrix(
        returns=returns,
        symbols=ordered_symbols,
        cfg=cfg,
    )
    distance = _build_distance_matrix(corr=corr, cfg=cfg)
    clusters = _agglomerative_clusters(distance=distance, symbols=ordered_symbols, cfg=cfg)
    clusters = _merge_small_clusters(clusters=clusters, distance=distance, cfg=cfg)
    return _label_clusters(
        clusters=clusters, symbols=ordered_symbols, corr=corr, distance=distance, cfg=cfg
    )


def build_correlation_clusters_cached(
    *,
    cache: Cache,
    ohlcv_map: dict[str, pd.DataFrame],
    symbols: list[str],
    as_of: date,
    policy: Policy,
    market_snapshot_id: str,
) -> CorrelationClusterResult:
    """Build clusters with deterministic cache lookup/write-through."""
    payload = cache_payload(
        symbols=symbols,
        as_of=as_of,
        policy=policy,
        market_snapshot_id=market_snapshot_id,
    )
    cached = cache.get("clusters", payload)
    if cached is not None:
        return result_from_payload(cached)

    result = build_correlation_clusters(
        ohlcv_map=ohlcv_map,
        symbols=symbols,
        as_of=as_of,
        policy=policy,
        market_snapshot_id=market_snapshot_id,
    )
    cache.put("clusters", payload, result_to_payload(as_of, result))
    return result


def _build_returns(
    *,
    ohlcv_map: dict[str, pd.DataFrame],
    symbols: list[str],
    as_of: date,
    cfg: ClusterConfig,
) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    as_of_ts = pd.Timestamp(as_of, tz="UTC")
    for sym in symbols:
        df = ohlcv_map[sym].sort_index()
        close = pd.to_numeric(df["Close"], errors="coerce")
        close.index = pd.to_datetime(close.index, utc=True)
        close = close.loc[close.index <= as_of_ts]
        if cfg.returns_method == "log":
            ret = np.log(close / close.shift(1))
        else:
            ret = close.pct_change()
        ret = ret.replace([np.inf, -np.inf], np.nan)
        if cfg.winsorize_pct > 0:
            lo = float(ret.quantile(cfg.winsorize_pct))
            hi = float(ret.quantile(1.0 - cfg.winsorize_pct))
            ret = ret.clip(lower=lo, upper=hi)
        out[sym] = ret.tail(cfg.window_days)
    return out


def _build_corr_matrix(
    *,
    returns: dict[str, pd.Series],
    symbols: list[str],
    cfg: ClusterConfig,
) -> pd.DataFrame:
    n = len(symbols)
    corr = np.eye(n, dtype=float)
    for i, j in combinations(range(n), 2):
        si = symbols[i]
        sj = symbols[j]
        pair = pd.concat([returns[si], returns[sj]], axis=1, join="inner")
        if cfg.nan_policy == "pairwise_drop":
            pair = pair.dropna()
            valid = len(pair) >= cfg.min_overlap_days
        else:
            valid = len(pair) >= cfg.window_days and not pair.isna().any().any()

        if not valid:
            cij = 0.0
        else:
            cij = float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method=cfg.corr_method))
            if not np.isfinite(cij):
                cij = 0.0
        corr_val = round(max(-1.0, min(1.0, cij)), cfg.distance_decimals)
        corr[i, j] = corr_val
        corr[j, i] = corr_val
    return pd.DataFrame(corr, index=symbols, columns=symbols)


def _build_distance_matrix(*, corr: pd.DataFrame, cfg: ClusterConfig) -> pd.DataFrame:
    if cfg.distance == "one_minus_corr":
        distance = 1.0 - corr
    else:
        distance = 1.0 - corr
    distance = distance.clip(lower=0.0, upper=2.0).round(cfg.distance_decimals)
    for sym in distance.index:
        distance.loc[sym, sym] = 0.0
    return distance


def _agglomerative_clusters(
    *,
    distance: pd.DataFrame,
    symbols: list[str],
    cfg: ClusterConfig,
) -> list[tuple[str, ...]]:
    active: dict[int, tuple[str, ...]] = {idx: (sym,) for idx, sym in enumerate(symbols)}
    next_id = len(active)

    while len(active) > 1:
        if cfg.cluster_cut_mode == "max_clusters" and len(active) <= cfg.max_clusters:
            break
        best = _best_merge(active=active, distance=distance)
        if best is None:
            break
        merge_dist, left_id, right_id = best
        if cfg.cluster_cut_mode == "distance_threshold" and merge_dist > cfg.distance_threshold:
            break

        merged = tuple(sorted(active[left_id] + active[right_id]))
        del active[left_id]
        del active[right_id]
        active[next_id] = merged
        next_id += 1

    return [tuple(sorted(cluster)) for cluster in active.values()]


def _best_merge(
    *,
    active: dict[int, tuple[str, ...]],
    distance: pd.DataFrame,
) -> tuple[float, int, int] | None:
    ids = sorted(active.keys())
    best: tuple[float, str, str, int, int] | None = None
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            left_cluster = active[left]
            right_cluster = active[right]
            d = round(_average_linkage_distance(left_cluster, right_cluster, distance), 6)
            a = min(left_cluster)
            b = min(right_cluster)
            first, second = (a, b) if a <= b else (b, a)
            candidate = (d, first, second, left, right)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        return None
    return best[0], best[3], best[4]


def _average_linkage_distance(
    cluster_a: Sequence[str],
    cluster_b: Sequence[str],
    distance: pd.DataFrame,
) -> float:
    vals = [float(distance.loc[a, b]) for a in cluster_a for b in cluster_b]
    return float(sum(vals) / max(1, len(vals)))


def _merge_small_clusters(
    *,
    clusters: list[tuple[str, ...]],
    distance: pd.DataFrame,
    cfg: ClusterConfig,
) -> list[tuple[str, ...]]:
    if cfg.min_cluster_size <= 1 or len(clusters) <= 1:
        return [tuple(sorted(cluster)) for cluster in clusters]

    working = [tuple(sorted(cluster)) for cluster in clusters]
    while True:
        small = sorted(
            [cluster for cluster in working if len(cluster) < cfg.min_cluster_size],
            key=lambda cluster: (len(cluster), min(cluster), cluster),
        )
        if not small or len(working) <= 1:
            break

        changed = False
        for cluster in small:
            if cluster not in working or len(working) <= 1:
                continue
            candidates = [other for other in working if other != cluster]
            nearest = min(
                candidates,
                key=lambda other: (
                    _average_linkage_distance(cluster, other, distance),
                    min(other),
                    other,
                ),
            )
            nearest_dist = _average_linkage_distance(cluster, nearest, distance)
            if nearest_dist > cfg.distance_threshold:
                continue
            merged = tuple(sorted(cluster + nearest))
            working.remove(cluster)
            working.remove(nearest)
            working.append(merged)
            changed = True
        if not changed:
            break
    return [tuple(sorted(cluster)) for cluster in working]


def _label_clusters(
    *,
    clusters: list[tuple[str, ...]],
    symbols: list[str],
    corr: pd.DataFrame,
    distance: pd.DataFrame,
    cfg: ClusterConfig,
) -> CorrelationClusterResult:
    ranking_rows: list[tuple[tuple[str, ...], float, float, float]] = []
    for cluster in clusters:
        avg_corr, min_corr = _cluster_corr_stats(cluster, corr)
        avg_dist = _cluster_avg_distance(cluster, distance)
        ranking_rows.append((tuple(sorted(cluster)), avg_corr, min_corr, avg_dist))

    ordered = sorted(ranking_rows, key=lambda row: (-len(row[0]), row[3], min(row[0])))

    cluster_map: dict[str, str] = {}
    stats: list[ClusterStats] = []
    for idx, (cluster, avg_corr, min_corr, _avg_dist) in enumerate(ordered):
        cluster_id = f"{cfg.label_prefix}_{idx:0{cfg.label_width}d}"
        for sym in cluster:
            cluster_map[sym] = cluster_id
        stats.append(
            ClusterStats(
                cluster_id=cluster_id,
                size=len(cluster),
                symbols=list(cluster),
                avg_corr=round(avg_corr, 6),
                min_corr=round(min_corr, 6),
            )
        )

    final_map = {sym: cluster_map[sym] for sym in sorted(symbols)}
    return CorrelationClusterResult(
        cluster_map=final_map,
        cluster_stats=stats,
        cluster_map_hash=_stable_sha256(final_map),
    )


def _cluster_corr_stats(cluster: Sequence[str], corr: pd.DataFrame) -> tuple[float, float]:
    if len(cluster) <= 1:
        return 1.0, 1.0
    vals = [float(corr.loc[a, b]) for a, b in combinations(cluster, 2)]
    return float(sum(vals) / len(vals)), float(min(vals))


def _cluster_avg_distance(cluster: Sequence[str], distance: pd.DataFrame) -> float:
    if len(cluster) <= 1:
        return 0.0
    vals = [float(distance.loc[a, b]) for a, b in combinations(cluster, 2)]
    return float(sum(vals) / len(vals))


def expected_lookback_days(policy: Policy, default_days: int) -> int:
    cfg = config_from_policy(policy)
    return max(default_days, cfg.window_days + 30)

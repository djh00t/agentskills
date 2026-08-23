"""Correlation-cluster output models and JSON helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ClusterStats:
    """Summary statistics for a single correlation cluster."""

    cluster_id: str
    size: int
    symbols: list[str]
    avg_corr: float
    min_corr: float


@dataclass(frozen=True)
class CorrelationClusterResult:
    """Deterministic cluster assignment result."""

    cluster_map: dict[str, str]
    cluster_stats: list[ClusterStats]
    cluster_map_hash: str


def result_to_payload(as_of: date, result: CorrelationClusterResult) -> dict[str, Any]:
    """Serialize result dataclasses to a JSON-compatible payload."""
    return {
        "as_of": str(as_of),
        "cluster_map": dict(result.cluster_map),
        "cluster_stats": [asdict(stat) for stat in result.cluster_stats],
        "cluster_map_hash": result.cluster_map_hash,
    }


def result_from_payload(payload: dict[str, Any]) -> CorrelationClusterResult:
    """Deserialize a cached payload into cluster result dataclasses."""
    stats = [
        ClusterStats(
            cluster_id=str(item["cluster_id"]),
            size=int(item["size"]),
            symbols=[str(s) for s in item["symbols"]],
            avg_corr=float(item["avg_corr"]),
            min_corr=float(item.get("min_corr", 1.0)),
        )
        for item in payload.get("cluster_stats", [])
    ]
    return CorrelationClusterResult(
        cluster_map={str(k): str(v) for k, v in dict(payload.get("cluster_map", {})).items()},
        cluster_stats=stats,
        cluster_map_hash=str(payload["cluster_map_hash"]),
    )

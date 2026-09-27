"""Estimate inference cost from agent-brain inference_pricing.yaml.

Prefer provider-reported cost when present. Soft-import agent-brain loader when
available on PYTHONPATH; otherwise a minimal YAML reader matching that schema.
Never hard-code list prices into this module.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DEFAULT_PRICING_CANDIDATES = [
    Path.home()
    / "work/src/github.com_local/djh00t/agent-brain/config/inference_pricing.yaml",
    Path.home() / "work/src/github.com/djh00t/agent-brain/config/inference_pricing.yaml",
]


def default_pricing_path() -> Optional[Path]:
    env = os.environ.get("FSM_PRICING_PATH") or os.environ.get("INFERENCE_PRICING_PATH")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    for c in DEFAULT_PRICING_CANDIDATES:
        if c.is_file():
            return c
    return None


def _soft_estimate_via_agent_brain(
    tokens_in: int,
    tokens_out: int,
    model: str,
    *,
    tokens_cached_in: int = 0,
    batch: bool = False,
    path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    try:
        from pipelines.common.pricing.loader import estimate_cost  # type: ignore
    except Exception:
        return None
    try:
        return estimate_cost(
            tokens_in,
            tokens_out,
            model,
            batch=batch,
            tokens_cached_in=tokens_cached_in,
            path=str(path) if path else None,
        )
    except Exception:
        return None


@lru_cache(maxsize=4)
def _load_table_minimal(path_str: str) -> dict[str, dict[str, Any]]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML required to load inference_pricing.yaml") from exc
    raw = yaml.safe_load(Path(path_str).read_text(encoding="utf-8")) or {}
    out: dict[str, dict[str, Any]] = {}
    for entry in raw.get("models") or []:
        if not isinstance(entry, dict) or not entry.get("model_id"):
            continue
        if entry.get("price_per_1m_input_usd") is None:
            continue
        out[str(entry["model_id"])] = entry
    return out


def _estimate_minimal(
    tokens_in: int,
    tokens_out: int,
    model: str,
    *,
    tokens_cached_in: int = 0,
    batch: bool = False,
    path: Path,
) -> dict[str, Any]:
    table = _load_table_minimal(str(path))
    if model not in table:
        raise KeyError(f"unknown model_id={model!r}")
    entry = table[model]
    disc = float(entry["batch_discount"]) if (batch and entry.get("batch_discount") is not None) else 1.0
    pin = float(entry["price_per_1m_input_usd"]) * disc
    pout = float(entry["price_per_1m_output_usd"]) * disc
    pcached_raw = entry.get("price_per_1m_cached_input_usd")
    pcached = float(pcached_raw) * disc if pcached_raw is not None else None
    unc = max(0, int(tokens_in) - max(0, int(tokens_cached_in)))
    cached = max(0, int(tokens_cached_in))
    cost_in = (unc / 1_000_000.0) * pin
    cost_cached = 0.0
    if cached and pcached is not None:
        cost_cached = (cached / 1_000_000.0) * pcached
    elif cached:
        cost_in += (cached / 1_000_000.0) * pin
        cached = 0
    cost_out = (max(0, int(tokens_out)) / 1_000_000.0) * pout
    total = cost_in + cost_cached + cost_out
    return {
        "model": model,
        "batch": batch,
        "tokens_in": int(tokens_in),
        "tokens_out": int(tokens_out),
        "tokens_cached_in": int(tokens_cached_in),
        "usd_input": round(cost_in, 6),
        "usd_cached_input": round(cost_cached, 6),
        "usd_output": round(cost_out, 6),
        "usd_total": round(total, 6),
        "estimated_price_row": bool(entry.get("estimated")),
        "provider": str(entry.get("provider") or ""),
    }


def estimate_cost(
    tokens_in: int,
    tokens_out: int,
    model: str,
    *,
    tokens_cached_in: int = 0,
    batch: bool = False,
    path: Optional[Path] = None,
) -> dict[str, Any]:
    """Estimate USD cost. Soft-import agent-brain loader; else minimal YAML reader."""
    pricing = path or default_pricing_path()
    soft = _soft_estimate_via_agent_brain(
        tokens_in,
        tokens_out,
        model,
        tokens_cached_in=tokens_cached_in,
        batch=batch,
        path=pricing,
    )
    if soft is not None:
        return soft
    if pricing is None:
        raise FileNotFoundError("inference_pricing.yaml not found; set FSM_PRICING_PATH")
    return _estimate_minimal(
        tokens_in,
        tokens_out,
        model,
        tokens_cached_in=tokens_cached_in,
        batch=batch,
        path=pricing,
    )


def price_event(event: dict[str, Any]) -> dict[str, Any]:
    """Fill costTotal on an event dict. Mutates and returns the same dict.

    Rules:
    - billing_mode=subscription → costTotal=0, cost_is_plan=True
    - provider-reported costTotal already > 0 → keep it
    - else estimate from table when model + tokens present
    """
    mode = str(event.get("billing_mode") or "api").lower()
    if mode == "subscription":
        event["costTotal"] = 0.0
        event["cost_is_plan"] = True
        event["billing_mode"] = "subscription"
        return event

    reported = event.get("costTotal")
    try:
        reported_f = float(reported) if reported is not None else None
    except (TypeError, ValueError):
        reported_f = None
    if reported_f is not None and reported_f > 0:
        event["costTotal"] = reported_f
        event["cost_is_plan"] = False
        return event

    model = str(event.get("model") or "").strip()
    if not model:
        event.setdefault("costTotal", 0.0)
        return event

    try:
        est = estimate_cost(
            int(event.get("inputTokens") or 0),
            int(event.get("outputTokens") or 0),
            model,
            tokens_cached_in=int(event.get("cachedInputTokens") or 0),
        )
        event["costTotal"] = float(est["usd_total"])
        event["cost_estimated"] = True
        if not event.get("provider") and est.get("provider"):
            event["provider"] = est["provider"]
    except Exception:
        event.setdefault("costTotal", 0.0)
    return event

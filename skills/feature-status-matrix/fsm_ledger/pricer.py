"""Estimate inference cost from agent-brain inference_pricing.yaml.

Prefer provider-reported cost when present. Soft-import agent-brain loader when
available on PYTHONPATH; otherwise a minimal YAML reader matching that schema.
Never hard-code list prices into this module.
"""
from __future__ import annotations

import math
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
    tokens_cached_in: int | None = 0,
    tokens_cache_write_in: int | None = 0,
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
            tokens_cache_write_in=tokens_cache_write_in,
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
        row = dict(entry)
        if raw.get("as_of_default") is not None:
            row.setdefault("as_of_default", raw["as_of_default"])
        if raw.get("source_url") is not None:
            row.setdefault("source_url", raw["source_url"])
        out[str(entry["model_id"])] = row
    return out


def _estimate_minimal(
    tokens_in: int,
    tokens_out: int,
    model: str,
    *,
    tokens_cached_in: int | None = 0,
    tokens_cache_write_in: int | None = 0,
    batch: bool = False,
    path: Path,
) -> dict[str, Any]:
    table = _load_table_minimal(str(path))
    if model not in table:
        raise KeyError(f"unknown model_id={model!r}")
    entry = table[model]
    input_tokens = int(tokens_in)
    output_tokens = int(tokens_out)
    cache_read_unknown = tokens_cached_in is None
    cached = 0 if cache_read_unknown else int(tokens_cached_in)
    cache_write_unknown = tokens_cache_write_in is None
    cache_write = 0 if cache_write_unknown else int(tokens_cache_write_in)
    if min(input_tokens, output_tokens, cached, cache_write) < 0:
        raise ValueError("token counts must be nonnegative")
    if cached + cache_write > input_tokens:
        raise ValueError("cached and cache-write tokens exceed total input tokens")

    for key in ("price_per_1m_input_usd", "price_per_1m_output_usd"):
        value = entry.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{key} must be finite and nonnegative")
    for key in ("price_per_1m_cached_input_usd", "price_per_1m_cache_write_usd"):
        value = entry.get(key)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{key} must be finite and nonnegative")

    tiers = entry.get("context_tiers") or []
    for item in tiers:
        minimum = item.get("minimum_context_tokens")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            raise ValueError("minimum_context_tokens must be a positive integer")
        for key in (
            "price_per_1m_input_usd",
            "price_per_1m_output_usd",
            "price_per_1m_cached_input_usd",
            "price_per_1m_cache_write_usd",
        ):
            value = item.get(key)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{key} must be finite and nonnegative")
        if item.get("price_per_1m_input_usd") is None or item.get("price_per_1m_output_usd") is None:
            raise ValueError("context tier requires input and output prices")
    tier = max(
        (item for item in tiers if input_tokens >= item["minimum_context_tokens"]),
        key=lambda item: item["minimum_context_tokens"],
        default=None,
    )
    rates = {**entry, **tier} if tier else entry
    disc = float(entry["batch_discount"]) if (batch and entry.get("batch_discount") is not None) else 1.0
    if not math.isfinite(disc) or disc < 0:
        raise ValueError("batch_discount must be finite and nonnegative")
    pin = float(rates["price_per_1m_input_usd"]) * disc
    pout = float(rates["price_per_1m_output_usd"]) * disc
    pcached_raw = rates.get("price_per_1m_cached_input_usd")
    pcached = float(pcached_raw) * disc if pcached_raw is not None else None
    pcache_write_raw = rates.get("price_per_1m_cache_write_usd")
    pcache_write = float(pcache_write_raw) * disc if pcache_write_raw is not None else None
    if cache_write_unknown and input_tokens > cached and pcache_write is not None:
        raise ValueError(f"model {model!r} has input tokens but no reported cache-write count")
    if cache_read_unknown and input_tokens > cache_write and pcached is not None:
        raise ValueError(f"model {model!r} has input tokens but no reported cached-input count")
    unc = input_tokens - cached - cache_write
    cost_in = (unc / 1_000_000.0) * pin
    cost_cached = (cached / 1_000_000.0) * pcached if cached and pcached is not None else 0.0
    if cached and pcached is None:
        cost_in += (cached / 1_000_000.0) * pin
    if cache_write and pcache_write is None:
        raise ValueError(f"model {model!r} has cache-write tokens but no published cache-write rate")
    cost_cache_write = (cache_write / 1_000_000.0) * pcache_write if cache_write and pcache_write is not None else 0.0
    cost_out = (output_tokens / 1_000_000.0) * pout
    total = cost_in + cost_cached + cost_cache_write + cost_out
    pricing_date = next(
        (entry[key] for key in ("pricing_date", "effective_date", "price_date", "as_of", "as_of_default") if entry.get(key) is not None),
        "",
    )
    return {
        "model": model,
        "batch": batch,
        "tokens_in": input_tokens,
        "tokens_out": output_tokens,
        "tokens_cached_in": cached,
        "tokens_cache_write_in": cache_write,
        "usd_input": cost_in,
        "usd_cached_input": cost_cached,
        "usd_cache_write_input": cost_cache_write,
        "usd_output": cost_out,
        "usd_total": total,
        "estimated_price_row": bool(entry.get("estimated")),
        "provider": str(entry.get("provider") or ""),
        "source_url": entry.get("source_url"),
        "rates": {
            "price_per_1m_input_usd": pin,
            "price_per_1m_output_usd": pout,
            "price_per_1m_cached_input_usd": pcached,
            "price_per_1m_cache_write_usd": pcache_write,
        },
        "context_tier_min_tokens": tier.get("minimum_context_tokens") if tier else None,
        "pricing_date": str(pricing_date),
    }


def estimate_cost(
    tokens_in: int,
    tokens_out: int,
    model: str,
    *,
    tokens_cached_in: int | None = 0,
    tokens_cache_write_in: int | None = 0,
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
        tokens_cache_write_in=tokens_cache_write_in,
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
        tokens_cache_write_in=tokens_cache_write_in,
        batch=batch,
        path=pricing,
    )


def price_event(event: dict[str, Any]) -> dict[str, Any]:
    """Fill costTotal on an event dict. Mutates and returns the same dict.

    Rules:
    - billing_mode=subscription → costTotal=0, cost_is_plan=True
    - valid provider-reported costTotal, including zero → keep it
    - else estimate only when model and complete token usage are present
    """
    mode = str(event.get("billing_mode") or "api").lower()
    if mode == "subscription":
        event["costTotal"] = 0.0
        event["cost_is_plan"] = True
        event["billing_mode"] = "subscription"
        return event

    reported = event.get("costTotal")
    if reported is not None:
        try:
            if isinstance(reported, bool):
                raise ValueError("boolean cost")
            reported_f = float(reported)
        except (TypeError, ValueError, OverflowError):
            reported_f = float("nan")
        if not math.isfinite(reported_f) or reported_f < 0:
            event["costTotal"] = None
            event["cost_diagnostic"] = "invalid reported cost"
            event["cost_estimated"] = False
            event["cost_is_plan"] = False
            return event
        event["costTotal"] = reported_f
        event["cost_is_plan"] = False
        event.pop("cost_diagnostic", None)
        return event

    if event.get("cost_diagnostic"):
        event["costTotal"] = None
        event["cost_estimated"] = False
        event["cost_is_plan"] = False
        return event

    model = str(event.get("model") or "").strip()
    if (
        not model
        or event.get("inputTokens") is None
        or event.get("outputTokens") is None
        or "inputTokens" not in event
        or "outputTokens" not in event
    ):
        event["costTotal"] = None
        event["cost_diagnostic"] = "missing model or complete token usage"
        event["cost_estimated"] = False
        event["cost_is_plan"] = False
        return event

    try:
        est = estimate_cost(
            int(event["inputTokens"]),
            int(event["outputTokens"]),
            model,
            tokens_cached_in=(
                int(event["cachedInputTokens"])
                if event.get("cachedInputTokens") is not None
                else None
            ),
            tokens_cache_write_in=(
                int(event["cacheWriteInputTokens"])
                if event.get("cacheWriteInputTokens") is not None
                else None
            ),
        )
        estimate_value = est["usd_total"]
        if isinstance(estimate_value, bool):
            raise ValueError("invalid estimated cost")
        estimate_value = float(estimate_value)
        if not math.isfinite(estimate_value) or estimate_value < 0:
            raise ValueError("invalid estimated cost")
        event["costTotal"] = estimate_value
        event["cost_estimated"] = True
        event["cost_is_plan"] = False
        event.pop("cost_diagnostic", None)
        if est.get("source_url") is not None:
            event["source_url"] = est["source_url"]
        if est.get("rates") is not None:
            event["rates"] = est["rates"]
        pricing_date = est.get("pricing_date") or est.get("as_of")
        if pricing_date:
            event["pricing_date"] = pricing_date
        if not event.get("provider") and est.get("provider"):
            event["provider"] = est["provider"]
    except Exception as exc:
        event["costTotal"] = None
        event["cost_estimated"] = False
        event["cost_is_plan"] = False
        event["cost_diagnostic"] = str(exc)
    return event

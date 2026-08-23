from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pam.clusters.builder import build_correlation_clusters_cached, expected_lookback_days
from pam.clusters.models import result_to_payload
from pam.config import Policy
from pam.data.cache import Cache
from pam.data.yahoo import fetch_ohlcv
from pam.engine import EngineInputs, recommend_for_symbol
from pam.models import DailyBrief, MarketContext, PortfolioInput, WatchlistInput
from pam.reporting import render_brief_md
from temporalio import activity


@dataclass(frozen=True)
class WorkflowArgs:
    portfolio_json: str
    watchlist_json: str
    market_json: str
    policy_path: str
    cache_dir: str
    interval: str
    lookback_days: int
    out_dir: str


@dataclass(frozen=True)
class MarketDataRef:
    symbols: list[str]
    start: str
    end: str
    interval: str
    snapshot_id: str


@dataclass(frozen=True)
class BuildClustersArgs:
    workflow: WorkflowArgs
    market: MarketDataRef


@dataclass(frozen=True)
class ComputeDailyBriefArgs:
    workflow: WorkflowArgs
    market: MarketDataRef
    clusters_json: str = ""


@dataclass(frozen=True)
class DailyBriefContent:
    brief_json: str
    brief_md: str


@dataclass(frozen=True)
class PersistOutputsArgs:
    workflow: WorkflowArgs
    content: DailyBriefContent


def _read_cluster_map(path: str) -> dict[str, str]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    payload = json.loads(p.read_text(encoding="utf-8"))
    cluster_map = payload.get("cluster_map", {})
    return {str(sym): str(cid) for sym, cid in dict(cluster_map).items()}


@activity.defn
async def validate_inputs(args: WorkflowArgs) -> None:
    PortfolioInput.model_validate_json(Path(args.portfolio_json).read_text(encoding="utf-8"))
    WatchlistInput.model_validate_json(Path(args.watchlist_json).read_text(encoding="utf-8"))
    MarketContext.model_validate_json(Path(args.market_json).read_text(encoding="utf-8"))
    Policy.load(args.policy_path)


@activity.defn
async def fetch_market_data(args: WorkflowArgs) -> MarketDataRef:
    pol = Policy.load(args.policy_path)
    port = PortfolioInput.model_validate_json(Path(args.portfolio_json).read_text(encoding="utf-8"))
    wl = WatchlistInput.model_validate_json(Path(args.watchlist_json).read_text(encoding="utf-8"))
    symbols = sorted(set([h.symbol for h in port.holdings] + wl.symbols))

    end_d = port.as_of
    lookback_days = expected_lookback_days(pol, args.lookback_days)
    start_d = end_d - timedelta(days=lookback_days)
    cache = Cache(args.cache_dir)
    fetch_ohlcv(
        symbols=symbols,
        start=start_d,
        end=end_d + timedelta(days=1),
        interval=args.interval,
        cache=cache,
    )

    payload = {
        "symbols": sorted(symbols),
        "start": str(start_d),
        "end": str(end_d + timedelta(days=1)),
        "interval": args.interval,
    }
    snapshot_id = str((cache.get("yahoo_ohlcv", payload) or {}).get("_snapshot_id", ""))
    return MarketDataRef(
        symbols=symbols,
        start=str(start_d),
        end=str(end_d + timedelta(days=1)),
        interval=args.interval,
        snapshot_id=snapshot_id,
    )


@activity.defn(name="BuildCorrelationClustersActivity")
async def build_correlation_clusters_activity(args: BuildClustersArgs) -> str:
    wf = args.workflow
    market = args.market
    pol = Policy.load(wf.policy_path)
    if not bool(pol.get("correlation_clusters", "enabled", default=True)):
        return ""

    port = PortfolioInput.model_validate_json(Path(wf.portfolio_json).read_text(encoding="utf-8"))
    wl = WatchlistInput.model_validate_json(Path(wf.watchlist_json).read_text(encoding="utf-8"))
    symbols = sorted(set([h.symbol for h in port.holdings] + wl.symbols))
    holdings_by_sym = {h.symbol: h for h in port.holdings}
    missing = [
        sym
        for sym in symbols
        if (holdings_by_sym[sym].cluster if sym in holdings_by_sym else None) is None
    ]
    if not missing:
        return ""

    cache = Cache(wf.cache_dir)
    data = fetch_ohlcv(
        symbols=market.symbols,
        start=date.fromisoformat(market.start),
        end=date.fromisoformat(market.end),
        interval=market.interval,
        cache=cache,
    )
    ohlcv_map = {sym: data[sym].df for sym in market.symbols}
    result = build_correlation_clusters_cached(
        cache=cache,
        ohlcv_map=ohlcv_map,
        symbols=market.symbols,
        as_of=port.as_of,
        policy=pol,
        market_snapshot_id=market.snapshot_id,
    )

    out_dir = Path(wf.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "clusters.json"
    out_path.write_text(
        json.dumps(result_to_payload(port.as_of, result), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return str(out_path)


@activity.defn
async def compute_daily_brief(args: ComputeDailyBriefArgs) -> DailyBriefContent:
    wf = args.workflow
    market = args.market
    pol = Policy.load(wf.policy_path)
    port = PortfolioInput.model_validate_json(Path(wf.portfolio_json).read_text(encoding="utf-8"))
    mk = MarketContext.model_validate_json(Path(wf.market_json).read_text(encoding="utf-8"))

    cache = Cache(wf.cache_dir)
    data = fetch_ohlcv(
        symbols=market.symbols,
        start=date.fromisoformat(market.start),
        end=date.fromisoformat(market.end),
        interval=market.interval,
        cache=cache,
    )

    cluster_map = _read_cluster_map(args.clusters_json)
    holdings_by_sym = {h.symbol: h for h in port.holdings}
    for holding in port.holdings:
        if holding.cluster is None and cluster_map.get(holding.symbol):
            holding.cluster = cluster_map[holding.symbol]

    eng_in = EngineInputs(
        policy=pol,
        as_of=port.as_of,
        base_currency=port.base_currency,
        cash_available=port.cash_available,
        margin_available=port.margin_available,
    )
    recs, opps = [], []
    for sym in market.symbols:
        df = data[sym].df.dropna()
        if len(df) < 210:
            continue
        holding = holdings_by_sym.get(sym)
        rec = recommend_for_symbol(sym, df, holding, eng_in, mk.regime)
        if holding is None and cluster_map.get(sym):
            rec.diagnostics["cluster"] = cluster_map[sym]
        (recs if holding else opps).append(rec)

    total_cap = port.cash_available + sum(h.quantity * h.avg_price for h in port.holdings)
    cash_util = 0.0 if total_cap <= 0 else float(1.0 - (port.cash_available / total_cap))
    cash_util = max(0.0, min(1.0, cash_util))
    heats = [float(r.diagnostics.get("atr_pct", 0.0)) for r in recs]
    heat = min(1.0, sum(heats) / max(1, len(heats)) * 10.0)

    brief = DailyBrief(
        date=port.as_of,
        macro_mode=mk.regime,
        portfolio_heat=round(heat, 4),
        cash_utilisation=round(cash_util, 4),
        recommendations=recs,
        watchlist_opportunities=opps,
    )
    return DailyBriefContent(
        brief_json=brief.model_dump_json(indent=2, sort_keys=True),
        brief_md=render_brief_md(brief),
    )


@activity.defn
async def persist_outputs(args: PersistOutputsArgs) -> str:
    out_dir = Path(args.workflow.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "daily_brief.json"
    out_md = out_dir / "daily_brief.md"
    out_json.write_text(args.content.brief_json, encoding="utf-8")
    out_md.write_text(args.content.brief_md, encoding="utf-8")
    return str(out_json)

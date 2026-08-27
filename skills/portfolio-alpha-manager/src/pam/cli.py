from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Dict, Sequence, cast

# Support direct execution via `python src/pam/cli.py ...`.
if __package__ in {None, ""}:
    src_root = Path(__file__).resolve().parents[1]
    src_text = str(src_root)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"invalid date: {value} (expected YYYY-MM-DD)") from err


def _market_cache_payload(
    *,
    symbols: Sequence[str],
    start: str,
    end: str,
    interval: str,
) -> Dict[str, object]:
    return {
        "symbols": sorted(set(symbols)),
        "start": start,
        "end": end,
        "interval": interval,
    }


def _snapshot_from_cache(
    *,
    cache: object,
    symbols: Sequence[str],
    start: str,
    end: str,
    interval: str,
) -> str:
    payload = _market_cache_payload(
        symbols=symbols,
        start=start,
        end=end,
        interval=interval,
    )
    snapshot_payload = cache.get("yahoo_ohlcv", payload) or {}
    return str(snapshot_payload.get("_snapshot_id", ""))


def _normalize_symbols(raw: Sequence[str]) -> list[str]:
    out: set[str] = set()
    for item in raw:
        for sym in item.split(","):
            cleaned = sym.strip()
            if cleaned:
                out.add(cleaned)
    return sorted(out)


def _symbol_cluster(holding_cluster: str | None, mapping: object | None) -> str | None:
    if holding_cluster:
        return holding_cluster
    if mapping is None:
        return None
    mapped_cluster = getattr(mapping, "cluster", None)
    if not mapped_cluster:
        return None
    return str(mapped_cluster)


def _print_missing_dependency(err: ModuleNotFoundError) -> None:
    missing = err.name or "unknown"
    print(f"Missing Python dependency: {missing}", file=sys.stderr)
    print("Bootstrap this skill runtime:", file=sys.stderr)
    print("  bash scripts/bootstrap_openclaw.sh", file=sys.stderr)
    print("Manual fallback install:", file=sys.stderr)
    print(
        "  /home/node/.local/bin/python -m pip install --user --break-system-packages -e .",
        file=sys.stderr,
    )
    print("If `pip` is missing, bootstrap it first:", file=sys.stderr)
    print(
        "  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py",
        file=sys.stderr,
    )
    print(
        "  /home/node/.local/bin/python /tmp/get-pip.py --user --break-system-packages",
        file=sys.stderr,
    )


def _run_clusters_build(args: argparse.Namespace) -> int:
    from pam.clusters.builder import (
        build_correlation_clusters_cached,
        expected_lookback_days,
    )
    from pam.clusters.models import result_to_payload
    from pam.config import Policy
    from pam.data.cache import Cache
    from pam.data.yahoo import fetch_ohlcv

    pol = Policy.load(args.policy)
    universe = _normalize_symbols(args.symbols)
    if len(universe) < 2:
        raise ValueError("At least two symbols are required.")

    as_of_d = args.as_of
    lookback_days = expected_lookback_days(pol, args.days)
    start = as_of_d - timedelta(days=lookback_days)
    end = as_of_d

    cache = Cache(args.cache_dir)
    data = fetch_ohlcv(
        symbols=universe,
        start=start,
        end=end + timedelta(days=1),
        interval=args.interval,
        cache=cache,
    )
    snapshot_id = _snapshot_from_cache(
        cache=cache,
        symbols=universe,
        start=str(start),
        end=str(end + timedelta(days=1)),
        interval=args.interval,
    )
    ohlcv_map = {sym: data[sym].df for sym in universe}
    cluster_out = build_correlation_clusters_cached(
        cache=cache,
        ohlcv_map=ohlcv_map,
        symbols=universe,
        as_of=as_of_d,
        policy=pol,
        market_snapshot_id=snapshot_id,
    )

    Path(args.out_path).write_text(
        json.dumps(result_to_payload(as_of_d, cluster_out), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {args.out_path}")
    return 0


def _run_daily(args: argparse.Namespace) -> int:
    from pam.audit import build_input_hashes
    from pam.clusters.builder import (
        build_correlation_clusters_cached,
        config_from_policy,
        expected_lookback_days,
    )
    from pam.clusters.models import result_to_payload
    from pam.config import Policy
    from pam.data.cache import Cache
    from pam.data.yahoo import fetch_ohlcv
    from pam.engine import EngineInputs, recommend_for_symbol
    from pam.fees import FeeConfig, Model, estimate_execution_cost
    from pam.mapping import load_symbol_map
    from pam.models import (
        AuditManifest,
        CorrelationClustersAudit,
        DailyBrief,
        Lot,
        MarketContext,
        Order,
        PortfolioInput,
        WatchlistInput,
    )
    from pam.optimizer import Constraints, build_target_weights
    from pam.reporting import render_brief_md
    from pam.tax_lots import Method, select_lots

    pol = Policy.load(args.policy)
    port = PortfolioInput.model_validate_json(Path(args.portfolio).read_text(encoding="utf-8"))
    wl = WatchlistInput.model_validate_json(Path(args.watchlist).read_text(encoding="utf-8"))
    mk = MarketContext.model_validate_json(Path(args.market).read_text(encoding="utf-8"))
    sym_map = load_symbol_map(args.symbol_map)

    for holding in port.holdings:
        meta = sym_map.get(holding.symbol)
        if not meta:
            continue
        if holding.sector is None:
            holding.sector = meta.sector
        if holding.cluster is None:
            holding.cluster = meta.cluster

    symbols = sorted(set([h.symbol for h in port.holdings] + wl.symbols))
    end = port.as_of
    lookback_days = expected_lookback_days(pol, args.days)
    start = end - timedelta(days=lookback_days)

    cache = Cache(args.cache_dir)
    data = fetch_ohlcv(
        symbols=symbols,
        start=start,
        end=end + timedelta(days=1),
        interval=args.interval,
        cache=cache,
    )
    ohlcv_map = {sym: data[sym].df for sym in symbols}
    market_snapshot_id = _snapshot_from_cache(
        cache=cache,
        symbols=symbols,
        start=str(start),
        end=str(end + timedelta(days=1)),
        interval=args.interval,
    )

    holdings_by_sym = {h.symbol: h for h in port.holdings}
    cluster_out = None
    cluster_enabled = bool(pol.get("correlation_clusters", "enabled", default=True))
    missing_cluster_symbols = [
        sym
        for sym in symbols
        if _symbol_cluster(
            holdings_by_sym[sym].cluster if sym in holdings_by_sym else None,
            sym_map.get(sym),
        )
        is None
    ]
    if cluster_enabled and missing_cluster_symbols:
        cluster_out = build_correlation_clusters_cached(
            cache=cache,
            ohlcv_map=ohlcv_map,
            symbols=symbols,
            as_of=port.as_of,
            policy=pol,
            market_snapshot_id=market_snapshot_id,
        )
        for holding in port.holdings:
            if holding.cluster is None:
                holding.cluster = cluster_out.cluster_map.get(holding.symbol)

    eng_in = EngineInputs(
        policy=pol,
        as_of=port.as_of,
        base_currency=port.base_currency,
        cash_available=port.cash_available,
        margin_available=port.margin_available,
    )

    recs = []
    opps = []
    for sym in symbols:
        df = data[sym].df.dropna()
        if len(df) < 210:
            continue
        holding = holdings_by_sym.get(sym)
        rec = recommend_for_symbol(sym, df, holding, eng_in, mk.regime)
        if holding is not None:
            recs.append(rec)
        else:
            meta = sym_map.get(sym)
            if meta:
                if meta.sector is not None:
                    rec.diagnostics["sector"] = meta.sector
                if meta.cluster is not None:
                    rec.diagnostics["cluster"] = meta.cluster
            if cluster_out is not None and rec.diagnostics.get("cluster") is None:
                rec.diagnostics["cluster"] = cluster_out.cluster_map.get(sym)
            opps.append(rec)

    cons = Constraints(
        max_asset_pct=float(pol.get("capital", "max_asset_pct")),
        max_sector_pct=float(pol.get("capital", "max_sector_pct")),
        max_cluster_pct=float(pol.get("capital", "max_cluster_pct")),
        max_new_trade_pct=float(pol.get("capital", "max_new_trade_pct")),
    )

    total_cap = port.cash_available + sum(h.quantity * h.avg_price for h in port.holdings)
    cash_util = 0.0 if total_cap <= 0 else float(1.0 - (port.cash_available / total_cap))
    cash_util = max(0.0, min(1.0, cash_util))

    heats = [float(r.diagnostics.get("atr_pct", 0.0)) for r in recs]
    heat = min(1.0, sum(heats) / max(1, len(heats)) * 10.0)
    defensive = heat >= float(pol.get("risk", "portfolio_heat_defensive"))
    target_weights = build_target_weights(recs, opps, cons, defensive=defensive)

    current_weights: Dict[str, float] = {}
    for holding in port.holdings:
        current_weights[holding.symbol] = (
            0.0 if total_cap <= 0 else (holding.quantity * holding.avg_price) / total_cap
        )

    cluster_exposure: Dict[str, float] = {}
    for holding in port.holdings:
        cluster = holding.cluster or "UNKNOWN"
        cluster_exposure[cluster] = cluster_exposure.get(cluster, 0.0) + current_weights.get(
            holding.symbol, 0.0
        )
    risk_alerts: list[str] = []
    for cluster, weight in sorted(cluster_exposure.items()):
        if weight > cons.max_cluster_pct + 1e-9:
            risk_alerts.append(
                f"Cluster exposure {cluster}={weight:.4f} exceeds cap {cons.max_cluster_pct:.4f}."
            )

    fee_model = str(pol.get("costs", "fee_model", default="flat"))
    if fee_model not in {"flat", "ibkr_us_tiered", "ibkr_au_asx"}:
        fee_model = "flat"
    fee_cfg = FeeConfig(
        model=cast(Model, fee_model),
        flat_fee=float(pol.get("costs", "per_trade_fee", default=1.0)),
        slippage_bps=float(pol.get("costs", "slippage_bps", default=5)),
    )

    orders: list[dict[str, object]] = []
    allowed_methods: set[str] = {
        "FIFO",
        "LIFO",
        "MIN_TAX",
        "HARVEST_LOSS",
        "MIN_GAIN",
        "MAX_GAIN",
    }
    lot_method_raw = str(pol.get("tax", "lot_selection_method", default="MIN_TAX"))
    if lot_method_raw in allowed_methods:
        lot_method: Method = cast(Method, lot_method_raw)
    else:
        lot_method = "MIN_TAX"
    long_term_days = int(pol.get("tax", "au_long_term_days"))

    for rec in recs:
        sym = rec.symbol
        cur_w = float(current_weights.get(sym, 0.0))
        tgt_w = float(target_weights.get(sym, 0.0))
        if rec.action in ("SELL",) or (cur_w > tgt_w and (cur_w - tgt_w) > 0.002):
            holding = holdings_by_sym[sym]
            sell_value = max(0.0, (cur_w - tgt_w) * total_cap)
            sell_qty = min(holding.quantity, sell_value / max(0.0001, holding.avg_price))
            sell_qty = round(sell_qty, 6)
            if sell_qty <= 0:
                continue

            lots = holding.lots or [
                Lot(
                    lot_id="LOT0",
                    quantity=holding.quantity,
                    cost_basis=holding.avg_price,
                    purchase_date=holding.purchase_date,
                )
            ]
            ref_price = float(rec.diagnostics.get("price", holding.avg_price))
            selected = select_lots(
                lots,
                sell_qty=sell_qty,
                as_of=port.as_of,
                current_price=ref_price,
                long_term_days=long_term_days,
                method=lot_method,
            )
            tax_lots = [
                {
                    "lot_id": s.lot_id,
                    "quantity": s.quantity,
                    "purchase_date": str(s.purchase_date),
                    "cost_basis": s.cost_basis,
                }
                for s in selected
            ]
            notional = sell_qty * ref_price
            est_fee = estimate_execution_cost(fee_cfg, notional=notional, shares=sell_qty)
            orders.append(
                {
                    "symbol": sym,
                    "side": "SELL",
                    "quantity": sell_qty,
                    "limit_range": [float(x) for x in rec.exit_range],
                    "estimated_fees": round(est_fee, 4),
                    "tax_lots": tax_lots,
                }
            )

    cash_remaining = port.cash_available
    for rec in recs + opps:
        sym = rec.symbol
        tgt_w = float(target_weights.get(sym, 0.0))
        cur_w = float(current_weights.get(sym, 0.0))
        if rec.action in ("BUY", "ACCUMULATE") and tgt_w > cur_w:
            add_value = (tgt_w - cur_w) * total_cap
            add_value = min(add_value, cash_remaining)
            if add_value <= 0:
                continue
            est_price = float(rec.diagnostics.get("price", sum(rec.entry_range) / 2))
            buy_qty = round(add_value / max(0.0001, est_price), 6)
            if buy_qty <= 0:
                continue
            notional = buy_qty * est_price
            est_fee = estimate_execution_cost(fee_cfg, notional=notional, shares=buy_qty)
            orders.append(
                {
                    "symbol": sym,
                    "side": "BUY",
                    "quantity": buy_qty,
                    "limit_range": [float(x) for x in rec.entry_range],
                    "estimated_fees": round(est_fee, 4),
                    "tax_lots": [],
                }
            )
            cash_remaining = max(0.0, cash_remaining - notional - est_fee)

    brief = DailyBrief(
        date=port.as_of,
        macro_mode=mk.regime,
        portfolio_heat=round(heat, 4),
        cash_utilisation=round(cash_util, 4),
        recommendations=recs,
        watchlist_opportunities=opps,
        risk_alerts=risk_alerts,
        notes=[],
    )
    brief.trade_plan.target_weights = {
        sym: round(weight, 6) for sym, weight in target_weights.items()
    }
    brief.trade_plan.orders = [Order(**order) for order in orders]

    try:
        code_ver = pkg_version("portfolio-alpha-manager")
    except PackageNotFoundError:
        code_ver = "0.0.0+unknown"

    input_hashes = build_input_hashes(
        {
            "portfolio": args.portfolio,
            "watchlist": args.watchlist,
            "market": args.market,
            "policy": args.policy,
            **({"symbol_map": args.symbol_map} if args.symbol_map else {}),
        }
    )
    cluster_cfg = config_from_policy(pol)
    brief.audit = AuditManifest(
        date=port.as_of,
        code_version=code_ver,
        policy_version=str(pol.get("version")),
        input_hashes=input_hashes,
        market_snapshot_id=market_snapshot_id,
        correlation_clusters=(
            CorrelationClustersAudit(
                window_days=cluster_cfg.window_days,
                distance_threshold=cluster_cfg.distance_threshold,
                cluster_map_hash=cluster_out.cluster_map_hash,
                snapshot_id=market_snapshot_id,
                policy_version=str(pol.get("version")),
            )
            if cluster_out is not None
            else None
        ),
    )

    Path(args.out_json).write_text(
        brief.model_dump_json(indent=2, sort_keys=True), encoding="utf-8"
    )
    Path(args.out_md).write_text(render_brief_md(brief), encoding="utf-8")
    Path(args.out_audit).write_text(
        brief.audit.model_dump_json(indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.out_clusters and cluster_out is not None:
        Path(args.out_clusters).write_text(
            json.dumps(result_to_payload(port.as_of, cluster_out), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(f"Wrote {args.out_json}, {args.out_md}, and {args.out_audit}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pam")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("daily", help="Generate deterministic daily brief and trade plan.")
    daily.add_argument("--portfolio", required=True)
    daily.add_argument("--watchlist", required=True)
    daily.add_argument("--market", required=True)
    daily.add_argument("--policy", default="configs/policy.default.json")
    daily.add_argument("--cache-dir", default=".cache/pam")
    daily.add_argument("--days", type=int, default=365)
    daily.add_argument("--interval", default="1d")
    daily.add_argument("--out-json", default="daily_brief.json")
    daily.add_argument("--out-md", default="daily_brief.md")
    daily.add_argument("--symbol-map", default=None)
    daily.add_argument("--out-audit", default="audit_manifest.json")
    daily.add_argument("--out-clusters", default=None)
    daily.set_defaults(handler=_run_daily)

    clusters = sub.add_parser("clusters", help="Correlation cluster builder tools.")
    clusters_sub = clusters.add_subparsers(dest="clusters_command", required=True)
    clusters_build = clusters_sub.add_parser("build", help="Build deterministic clusters.")
    clusters_build.add_argument(
        "--symbols",
        action="append",
        required=True,
        help="Repeat option or pass CSV symbols.",
    )
    clusters_build.add_argument("--as-of", type=_parse_date, required=True)
    clusters_build.add_argument("--policy", default="configs/policy.default.json")
    clusters_build.add_argument("--cache-dir", default=".cache/pam")
    clusters_build.add_argument("--days", type=int, default=365)
    clusters_build.add_argument("--interval", default="1d")
    clusters_build.add_argument("--out", dest="out_path", default="clusters.json")
    clusters_build.set_defaults(handler=_run_clusters_build)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return int(handler(args))
    except ModuleNotFoundError as err:
        _print_missing_dependency(err)
        return 2
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

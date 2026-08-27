from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class Lot(BaseModel):
    lot_id: str
    quantity: float
    cost_basis: float
    purchase_date: date


class Holding(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    purchase_date: date
    sector: Optional[str] = None
    cluster: Optional[str] = None
    lots: Optional[List[Lot]] = None


class PortfolioInput(BaseModel):
    as_of: date
    base_currency: str = Field(min_length=3, max_length=3)
    cash_available: float
    margin_available: float
    holdings: List[Holding]


class WatchlistInput(BaseModel):
    as_of: date
    symbols: List[str] = Field(min_length=1)


MacroMode = Literal["RISK_ON", "RISK_OFF", "NEUTRAL"]


class MarketContext(BaseModel):
    as_of: date
    regime: MacroMode
    volatility_proxy: Optional[str] = None
    volatility_value: Optional[float] = None
    benchmark: Optional[str] = None


Action = Literal["ACCUMULATE", "BUY", "HOLD", "TRIM", "SELL"]


class Recommendation(BaseModel):
    symbol: str
    action: Action
    confidence: float
    entry_range: Tuple[float, float]
    exit_range: Tuple[float, float]
    hard_stop: float
    trailing_stop: str
    position_size_pct: float
    reward_risk_ratio: float
    tax_note: str
    fees_note: str
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class Order(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    limit_range: Tuple[float, float]
    estimated_fees: float
    tax_lots: List[Dict[str, Any]] = Field(default_factory=list)


class AuditManifest(BaseModel):
    date: date
    code_version: str
    policy_version: str
    input_hashes: Dict[str, str]
    market_snapshot_id: str
    correlation_clusters: CorrelationClustersAudit | None = None


class TradePlan(BaseModel):
    orders: List[Order] = Field(default_factory=list)
    target_weights: Dict[str, float] = Field(default_factory=dict)


class CorrelationClustersAudit(BaseModel):
    window_days: int
    distance_threshold: float
    cluster_map_hash: str
    snapshot_id: str
    policy_version: str


class DailyBrief(BaseModel):
    date: date
    macro_mode: MacroMode
    portfolio_heat: float
    cash_utilisation: float
    recommendations: List[Recommendation]
    watchlist_opportunities: List[Recommendation]
    trade_plan: TradePlan = Field(default_factory=TradePlan)
    audit: AuditManifest | None = None
    risk_alerts: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

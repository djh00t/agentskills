from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf
from pam.data.cache import Cache


@dataclass(frozen=True)
class OHLCV:
    df: pd.DataFrame  # columns: Open, High, Low, Close, Volume; index: DatetimeIndex


def market_snapshot_id(serialized: Dict[str, list]) -> str:
    blob = json.dumps(serialized, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(blob).hexdigest()


def fetch_ohlcv(
    symbols: List[str],
    start: date,
    end: date,
    interval: str,
    cache: Optional[Cache] = None,
) -> Dict[str, OHLCV]:
    payload = {
        "symbols": sorted(symbols),
        "start": str(start),
        "end": str(end),
        "interval": interval,
    }
    if cache:
        cached = cache.get("yahoo_ohlcv", payload)
        if cached is not None:
            _snapshot = str(cached.get("_snapshot_id", ""))
            out: Dict[str, OHLCV] = {}
            for sym, rows in cached.items():
                if sym.startswith("_"):
                    continue
                df = pd.DataFrame(rows)
                df["Date"] = pd.to_datetime(df["Date"], utc=True)
                df = df.set_index("Date")
                out[sym] = OHLCV(df=df)
            return out

    out: Dict[str, OHLCV] = {}
    for sym in symbols:
        t = yf.Ticker(sym)
        df = t.history(start=str(start), end=str(end), interval=interval, auto_adjust=False)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index = pd.to_datetime(df.index, utc=True)
        out[sym] = OHLCV(df=df)

    if cache:
        serial: Dict[str, List[Dict[str, float]]] = {}
        for sym, ohlcv in out.items():
            dfx = ohlcv.df.reset_index().rename(columns={"index": "Date"})
            dfx["Date"] = dfx["Date"].astype(str)
            serial[sym] = dfx.to_dict(orient="records")
        snapshot = market_snapshot_id(serial)  # deterministic digest for audit manifests
        serial["_snapshot_id"] = snapshot  # type: ignore[index]
        cache.put("yahoo_ohlcv", payload, serial)

    return out

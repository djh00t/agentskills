from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class SymMeta:
    sector: Optional[str] = None
    cluster: Optional[str] = None


def load_symbol_map(path: str | Path | None) -> Dict[str, SymMeta]:
    if not path:
        return {}
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    out: Dict[str, SymMeta] = {}
    for sym, meta in data.items():
        out[sym] = SymMeta(
            sector=meta.get("sector"),
            cluster=meta.get("cluster"),
        )
    return out

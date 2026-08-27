from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class Policy:
    raw: Dict[str, Any]

    @staticmethod
    def load(path: str | Path) -> "Policy":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if "version" not in data:
            raise ValueError("Policy missing 'version'")
        return Policy(raw=data)

    def get(self, *keys: str, default: Any = None) -> Any:
        cur: Any = self.raw
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

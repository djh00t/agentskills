from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


class Cache:
    def __init__(self, root: str | Path):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _key(self, payload: Dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
        return hashlib.sha256(blob).hexdigest()

    def get(self, namespace: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._key(payload)
        path = self._root / namespace / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, namespace: str, payload: Dict[str, Any], value: Dict[str, Any]) -> Dict[str, Any]:
        key = self._key(payload)
        ns = self._root / namespace
        ns.mkdir(parents=True, exist_ok=True)
        path = ns / f"{key}.json"
        path.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")
        return value

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def build_input_hashes(paths: Dict[str, str]) -> Dict[str, str]:
    return {name: sha256_file(path) for name, path in paths.items()}

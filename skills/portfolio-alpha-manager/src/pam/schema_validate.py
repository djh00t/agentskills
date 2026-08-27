from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema


def load_schema(schema_path: Path) -> Dict[str, Any]:
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_json(instance_path: str | Path, schema_path: str | Path) -> None:
    inst = json.loads(Path(instance_path).read_text(encoding="utf-8"))
    schema = load_schema(Path(schema_path))
    jsonschema.validate(instance=inst, schema=schema)

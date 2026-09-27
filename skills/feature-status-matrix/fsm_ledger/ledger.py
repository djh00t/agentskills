\
"""Append-only JSONL usage ledger under ~/.agents/status-matrices/<project>/."""
from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .attribute import matrices_root, resolve_attribution
from .pricer import price_event
from .schema import UsageEvent, normalize_event

LOG_NAME = "_fsm-ledger.log"


def _log(msg: str) -> None:
    try:
        root = matrices_root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / LOG_NAME
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{ts} {msg}\n")
    except Exception:
        pass


def usage_log_path(project: str) -> Path:
    return matrices_root() / project / "usage.jsonl"


def _existing_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for key in ("event_id", "message_id"):
                    val = row.get(key)
                    if val:
                        ids.add(f"{key}:{val}")
    except OSError as exc:
        _log(f"read_ids_error path={path} err={exc}")
    return ids


def append_event(event: UsageEvent, *, project: Optional[str] = None) -> dict[str, Any]:
    """Append a UsageEvent. Never raises into caller. Returns result dict."""
    try:
        return append_dict(event.to_dict(), project=project or event.project or None)
    except Exception as exc:  # noqa: BLE001 — never raise into caller
        _log(f"append_event_error err={exc}\n{traceback.format_exc()}")
        return {"ok": False, "error": str(exc)}


def append_dict(raw: dict[str, Any], *, project: Optional[str] = None) -> dict[str, Any]:
    """Normalize, price, attribute, dedupe, and append. Never raises into caller."""
    try:
        event = normalize_event(raw)
        cwd = event.cwd or os.environ.get("PWD") or os.getcwd()
        attr = resolve_attribution(
            cwd=cwd,
            project=project or event.project or None,
            wp=None if event.workPackageId in ("",) else event.workPackageId,
        )
        # Only override WP if caller left default/empty — keep explicit UNALLOCATED
        if not raw.get("workPackageId") and not raw.get("work_package_id") and not raw.get("wp"):
            event.workPackageId = attr["workPackageId"]
        proj = project or event.project or attr["project"]
        event.project = proj

        data = event.to_dict()
        price_event(data)

        path = usage_log_path(proj)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Dedupe by event_id / message_id — never drop spend on other rows
        seen = _existing_ids(path)
        eid = data.get("event_id")
        mid = data.get("message_id")
        if eid and f"event_id:{eid}" in seen:
            _log(f"dedupe_skip project={proj} event_id={eid}")
            return {"ok": True, "deduped": True, "project": proj, "event_id": eid, "path": str(path)}
        if mid and f"message_id:{mid}" in seen:
            _log(f"dedupe_skip project={proj} message_id={mid}")
            return {"ok": True, "deduped": True, "project": proj, "message_id": mid, "path": str(path)}

        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")

        _log(
            f"append project={proj} wp={data.get('workPackageId')} "
            f"cost={data.get('costTotal')} tokens={data.get('totalTokens')} "
            f"event_id={data.get('event_id')}"
        )
        return {
            "ok": True,
            "deduped": False,
            "project": proj,
            "workPackageId": data.get("workPackageId"),
            "event_id": data.get("event_id"),
            "costTotal": data.get("costTotal"),
            "path": str(path),
        }
    except Exception as exc:  # noqa: BLE001
        _log(f"append_dict_error err={exc}\n{traceback.format_exc()}")
        return {"ok": False, "error": str(exc)}

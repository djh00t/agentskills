"""UsageEvent schema for the shared status-matrix usage ledger."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

UNALLOCATED = "UNALLOCATED"

BILLING_MODES = frozenset({"api", "subscription"})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class UsageEvent:
    workPackageId: str = UNALLOCATED
    model: str = ""
    inputTokens: int = 0
    outputTokens: int = 0
    cachedInputTokens: int = 0
    totalTokens: int = 0
    costTotal: float = 0.0
    provider: str = ""
    harness: str = ""
    session_id: str = ""
    cwd: str = ""
    run_id: str = ""
    event_id: str = ""
    ts: str = ""
    billing_mode: str = "api"  # api | subscription
    status: str = ""
    message_id: str = ""
    # Non-schema helper flags (persisted for matrix "plan" display)
    cost_is_plan: bool = False
    cost_estimated: bool = False
    project: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:16]}"
        if not self.ts:
            self.ts = _utc_now_iso()
        if self.billing_mode not in BILLING_MODES:
            self.billing_mode = "api"
        if not self.workPackageId:
            self.workPackageId = UNALLOCATED
        if self.totalTokens <= 0:
            self.totalTokens = int(self.inputTokens or 0) + int(self.outputTokens or 0)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop empty optional strings that add noise, keep zeros/booleans
        out: dict[str, Any] = {}
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, str) and v == "" and k not in ("workPackageId", "event_id", "ts", "billing_mode"):
                continue
            out[k] = v
        return out


def normalize_event(raw: dict[str, Any]) -> UsageEvent:
    """Coerce a loose dict (hook payload / CLI JSON) into UsageEvent."""
    if not isinstance(raw, dict):
        raise TypeError("event must be a dict")

    def _int(key: str, *alts: str) -> int:
        for k in (key, *alts):
            if k in raw and raw[k] is not None:
                try:
                    return int(raw[k])
                except (TypeError, ValueError):
                    pass
        return 0

    def _float(key: str, *alts: str) -> float:
        for k in (key, *alts):
            if k in raw and raw[k] is not None:
                try:
                    return float(raw[k])
                except (TypeError, ValueError):
                    pass
        return 0.0

    def _str(key: str, *alts: str) -> str:
        for k in (key, *alts):
            if k in raw and raw[k] is not None:
                return str(raw[k])
        return ""

    inp = _int("inputTokens", "input_tokens", "prompt_tokens")
    out = _int("outputTokens", "output_tokens", "completion_tokens")
    cached = _int("cachedInputTokens", "cached_input_tokens", "cached_tokens")
    total = _int("totalTokens", "total_tokens")
    if total <= 0:
        total = inp + out

    return UsageEvent(
        workPackageId=_str("workPackageId", "work_package_id", "wp") or UNALLOCATED,
        model=_str("model", "model_id", "model_slug"),
        inputTokens=inp,
        outputTokens=out,
        cachedInputTokens=cached,
        totalTokens=total,
        costTotal=_float("costTotal", "cost_total", "usd_total", "cost"),
        provider=_str("provider"),
        harness=_str("harness"),
        session_id=_str("session_id", "sessionId"),
        cwd=_str("cwd", "cwd_path"),
        run_id=_str("run_id", "runId"),
        event_id=_str("event_id", "eventId"),
        ts=_str("ts", "timestamp", "time"),
        billing_mode=_str("billing_mode", "billingMode") or "api",
        status=_str("status"),
        message_id=_str("message_id", "messageId", "message_uuid"),
        cost_is_plan=bool(raw.get("cost_is_plan", False)),
        cost_estimated=bool(raw.get("cost_estimated", False)),
        project=_str("project", "project_id"),
    )

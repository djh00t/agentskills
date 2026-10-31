#!/usr/bin/env python3
"""Roll Codex model calls up into a per-turn cost + wall-clock ledger.

Tokens come from Codex rollouts (~/.codex/sessions/**/*.jsonl):
  turn_context.model, token_usage_record.usage (one row per model call),
  event_msg/task_complete.duration_ms + time_to_first_token_ms.
Cost is NOT re-priced here: costTotal is joined from the fsm-ledger
usage.jsonl files (~/.agents/status-matrices/*/usage.jsonl) on the event_id
the Codex hook writes, "codex:{session_id}:{response_id}". Those rows are
priced at API rates from the models.dev snapshot. A call with no priced row
is counted in calls_unpriced and the turn's cost_complete is false.

Stdlib only. Output: CSV (default) or JSONL on stdout.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

FIELDS = [
    "started_at", "session_id", "turn_id", "cwd", "model", "calls",
    "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens",
    "reasoning_tokens", "wall_clock_s", "ttft_s", "est_cost_usd",
    "calls_unpriced", "cost_complete", "pricing_date", "pricing_source",
]
USAGE_KEYS = {
    "input_tokens": "input_tokens",
    "cache_read_tokens": "cached_input_tokens",
    "cache_write_tokens": "cache_write_input_tokens",
    "output_tokens": "output_tokens",
    "reasoning_tokens": "reasoning_output_tokens",
}


def as_int(value) -> int:
    """Token count or 0; never raises on bad input (same rule as fsm-ledger)."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def event_id(session_id: str, response_id: str) -> str:
    return f"codex:{session_id}:{response_id}"


def _records(path: Path):
    with path.open(encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                yield rec


def load_prices(ledger_root: Path) -> dict[str, dict]:
    """event_id -> {cost, pricing_date, source} from priced fsm-ledger rows."""
    prices: dict[str, dict] = {}
    for usage in sorted(ledger_root.glob("*/usage.jsonl")):
        for row in _records(usage):
            eid, cost = row.get("event_id"), row.get("costTotal")
            if eid and isinstance(cost, (int, float)) and not isinstance(cost, bool):
                prices[str(eid)] = {
                    "cost": float(cost),
                    "pricing_date": str(row.get("pricing_date") or ""),
                    "source": str(row.get("source_url") or ""),
                }
    return prices


def turns_from_rollout(path: Path, prices: dict[str, dict]) -> list[dict]:
    session_id, cwd = "", ""
    turns: dict[str, dict] = {}

    def turn(tid: str) -> dict:
        if tid not in turns:
            turns[tid] = {k: 0 for k in USAGE_KEYS} | {
                "started_at": "", "session_id": session_id, "turn_id": tid,
                "cwd": cwd, "model": "", "calls": 0, "wall_clock_s": None,
                "ttft_s": None, "est_cost_usd": 0.0, "calls_unpriced": 0,
                "pricing_date": set(), "pricing_source": set(),
            }
        return turns[tid]

    for rec in _records(path):
        kind, data = rec.get("type"), rec.get("payload") or {}
        if not isinstance(data, dict):
            continue
        if kind == "session_meta":
            session_id = str(data.get("session_id") or data.get("id") or "")
            cwd = str(data.get("cwd") or "")
        elif kind == "turn_context" and data.get("turn_id"):
            t = turn(str(data["turn_id"]))
            t["model"] = str(data.get("model") or t["model"])
            t["cwd"] = str(data.get("cwd") or t["cwd"])
            t["started_at"] = t["started_at"] or str(rec.get("timestamp") or "")
        elif kind == "token_usage_record" and data.get("turn_id"):
            usage = data.get("usage")
            if not isinstance(usage, dict):
                continue
            t = turn(str(data["turn_id"]))
            for out_key, src_key in USAGE_KEYS.items():
                t[out_key] += as_int(usage.get(src_key))
            t["calls"] += 1
            sid = t["session_id"] or session_id
            price = prices.get(event_id(sid, str(data.get("response_id") or "")))
            if price is None:
                t["calls_unpriced"] += 1
            else:
                t["est_cost_usd"] += price["cost"]
                t["pricing_date"].add(price["pricing_date"])
                t["pricing_source"].add(price["source"])
        elif kind == "event_msg" and data.get("type") == "task_complete" and data.get("turn_id"):
            t = turn(str(data["turn_id"]))
            if isinstance(data.get("duration_ms"), int):
                t["wall_clock_s"] = data["duration_ms"] / 1000
            if isinstance(data.get("time_to_first_token_ms"), int):
                t["ttft_s"] = data["time_to_first_token_ms"] / 1000

    rows = []
    for t in turns.values():
        if not t["calls"]:
            continue  # ponytail: turns with no model call carry no cost; skip.
        t["session_id"] = t["session_id"] or session_id
        t["cost_complete"] = t["calls_unpriced"] == 0
        t["est_cost_usd"] = round(t["est_cost_usd"], 8)
        t["pricing_date"] = ";".join(sorted(x for x in t["pricing_date"] if x))
        t["pricing_source"] = ";".join(sorted(x for x in t["pricing_source"] if x))
        rows.append(t)
    return rows


def path_date(path: Path, sessions: Path) -> date | None:
    """Date from a rollout path like sessions/2026/10/31/rollout-*.jsonl."""
    parts = path.relative_to(sessions).parts[:3]
    try:
        return date(*(int(x) for x in parts))
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    home = Path.home()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions", type=Path, default=home / ".codex" / "sessions")
    ap.add_argument("--ledger-root", type=Path, default=home / ".agents" / "status-matrices")
    ap.add_argument("--since", type=date.fromisoformat, default=None,
                    help="only rollouts whose path date (YYYY/MM/DD) is on or after this ISO date, e.g. 2026-10-31")
    ap.add_argument("--format", choices=["csv", "jsonl"], default="csv")
    args = ap.parse_args(argv)

    prices = load_prices(args.ledger_root)
    rows = []
    for path in sorted(args.sessions.rglob("*.jsonl")):
        if args.since and (path_date(path, args.sessions) or date.min) < args.since:
            continue
        rows.extend(turns_from_rollout(path, prices))
    rows.sort(key=lambda r: r["started_at"])

    if args.format == "jsonl":
        for r in rows:
            print(json.dumps({k: r[k] for k in FIELDS}))
    else:
        w = csv.DictWriter(sys.stdout, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

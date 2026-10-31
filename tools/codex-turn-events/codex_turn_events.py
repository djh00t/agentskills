#!/usr/bin/env python3
"""Codex turn events: log each turn locally and push a short event to a webhook.

  hook stop                 Codex Stop hook (async). Appends a turn row (model,
                            tokens, wall clock) from transcript_path and POSTs
                            a turn_complete event.
  hook permission_request   Codex PermissionRequest hook. Appends and POSTs a
                            needs_approval event; its ts starts the human-wait clock.
  reconcile [--since DATE]  Re-scan ~/.codex/sessions since the last run, append
                            turn rows the hooks missed, print a JSON gap report.

Webhook URL and key are read at run time from env vars
CODEX_EVENTS_WEBHOOK_URL / CODEX_EVENTS_WEBHOOK_KEY, else from the macOS
Keychain (generic passwords, services codex-events-webhook-url /
codex-events-webhook-key). They are never printed, logged or stored.
Hooks always print {} and exit 0. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USAGE_KEYS = {
    "input_tokens": "input_tokens",
    "cache_read_tokens": "cached_input_tokens",
    "cache_write_tokens": "cache_write_input_tokens",
    "output_tokens": "output_tokens",
    "reasoning_tokens": "reasoning_output_tokens",
}
PR_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
TEXT_MAX = 200


def state_dir() -> Path:
    env = os.environ.get("CODEX_TURN_EVENTS_DIR")
    return Path(env).expanduser() if env else Path.home() / ".local" / "state" / "codex-turn-events"


def sessions_dir() -> Path:
    env = os.environ.get("CODEX_SESSIONS_DIR")
    return Path(env).expanduser() if env else Path.home() / ".codex" / "sessions"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def as_int(value) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def short(text, limit: int = TEXT_MAX) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append_jsonl(name: str, row: dict) -> None:
    path = state_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                yield rec


# ---------------------------------------------------------------- rollouts

def turns_from_rollout(path: Path, now: float | None = None) -> dict[str, dict]:
    """turn_id -> turn row. Wall clock is exact from task_complete, else
    approximate (now - task_started.started_at) while the turn is finishing."""
    session_id, cwd, turns = "", "", {}

    def turn(tid: str) -> dict:
        if tid not in turns:
            turns[tid] = {"session_id": session_id, "turn_id": tid, "cwd": cwd, "model": "",
                          "calls": 0, **{k: 0 for k in USAGE_KEYS}, "started_at": None,
                          "wall_clock_s": None, "wall_clock_exact": False, "error": None}
        return turns[tid]

    for rec in read_jsonl(path):
        kind, data = rec.get("type"), rec.get("payload")
        if not isinstance(data, dict):
            continue
        tid = str(data.get("turn_id") or "")
        if kind == "session_meta":
            session_id = str(data.get("session_id") or data.get("id") or "")
            cwd = str(data.get("cwd") or "")
        elif kind == "turn_context" and tid:
            t = turn(tid)
            t["model"] = str(data.get("model") or t["model"])
            t["cwd"] = str(data.get("cwd") or t["cwd"])
        elif kind == "token_usage_record" and tid:
            usage = data.get("usage")
            if not isinstance(usage, dict):
                continue
            t = turn(tid)
            t["calls"] += 1
            for out_key, src_key in USAGE_KEYS.items():
                t[out_key] += as_int(usage.get(src_key))
        elif kind == "event_msg" and tid and data.get("type") == "task_started":
            turn(tid)["started_at"] = as_int(data.get("started_at")) or None
        elif kind == "event_msg" and tid and data.get("type") == "task_complete":
            t = turn(tid)
            t["started_at"] = t["started_at"] or as_int(data.get("started_at")) or None
            if isinstance(data.get("duration_ms"), int):
                t["wall_clock_s"], t["wall_clock_exact"] = data["duration_ms"] / 1000, True
            if data.get("error"):
                t["error"] = short((data["error"] or {}).get("message") if isinstance(data["error"], dict) else data["error"])
    now = time.time() if now is None else now
    for t in turns.values():
        t["session_id"] = t["session_id"] or session_id
        if t["wall_clock_s"] is None and t["started_at"]:
            t["wall_clock_s"] = round(max(0.0, now - t["started_at"]), 3)
    return turns


def path_date(path: Path, root: Path) -> date | None:
    try:
        return date(*(int(x) for x in path.relative_to(root).parts[:3]))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- webhook

def secret(env_name: str, keychain_service: str) -> str:
    value = os.environ.get(env_name, "")
    if value or sys.platform != "darwin":
        return value
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", keychain_service, "-w"],
                             capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def post_event(body: dict) -> dict:
    """POST body; return {posted, post_status|post_error}. Never includes URL or key."""
    url = secret("CODEX_EVENTS_WEBHOOK_URL", "codex-events-webhook-url")
    if not url:
        return {"posted": False, "post_error": "no webhook url configured"}
    key = secret("CODEX_EVENTS_WEBHOOK_KEY", "codex-events-webhook-key")
    headers = {"Content-Type": "application/json", "User-Agent": "codex-turn-events/0.1"}
    if key:
        header = os.environ.get("CODEX_EVENTS_WEBHOOK_KEY_HEADER", "Authorization")
        headers[header] = f"Bearer {key}" if header.lower() == "authorization" else key
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"posted": 200 <= resp.status < 300, "post_status": resp.status}
    except urllib.error.HTTPError as exc:
        return {"posted": False, "post_status": exc.code}
    except Exception as exc:  # noqa: BLE001 - report the class only; messages can carry the URL
        return {"posted": False, "post_error": type(exc).__name__}


# ---------------------------------------------------------------- hooks

def on_stop(payload: dict) -> None:
    session_id, turn_id = str(payload.get("session_id") or ""), str(payload.get("turn_id") or "")
    transcript = payload.get("transcript_path")
    row = {}
    if transcript and Path(transcript).is_file():
        row = turns_from_rollout(Path(transcript)).get(turn_id, {})
    row = {**row, "session_id": session_id or row.get("session_id", ""), "turn_id": turn_id,
           "cwd": str(payload.get("cwd") or row.get("cwd") or ""),
           "model": str(payload.get("model") or row.get("model") or ""),
           "source": "hook", "ts": now_iso()}
    append_jsonl("turns.jsonl", row)
    message = str(payload.get("last_assistant_message") or "")
    pr = PR_URL.findall(message)
    body = {"source": "codex", "event": "turn_complete", "session_id": row["session_id"],
            "turn_id": turn_id, "task": Path(row["cwd"]).name if row["cwd"] else "",
            "cwd": row["cwd"], "model": row["model"], "status": "error" if row.get("error") else "completed",
            "pr_url": pr[-1] if pr else None, "summary": short(message),
            "tokens": {k: row.get(k, 0) for k in USAGE_KEYS}, "wall_clock_s": row.get("wall_clock_s"),
            "ts": row["ts"]}
    append_jsonl("events.jsonl", {k: body[k] for k in ("event", "session_id", "turn_id", "task", "status", "pr_url", "ts")}
                 | post_event(body))


def on_permission_request(payload: dict) -> None:
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    cwd = str(payload.get("cwd") or "")
    body = {"source": "codex", "event": "needs_approval", "session_id": str(payload.get("session_id") or ""),
            "turn_id": str(payload.get("turn_id") or ""), "task": Path(cwd).name if cwd else "", "cwd": cwd,
            "model": str(payload.get("model") or ""), "status": "waiting_for_human",
            "tool_name": str(payload.get("tool_name") or ""), "description": short(tool_input.get("description")),
            "wait_started_at": now_iso()}
    body["ts"] = body["wait_started_at"]
    append_jsonl("events.jsonl", {k: body[k] for k in ("event", "session_id", "turn_id", "task", "status",
                                                       "tool_name", "wait_started_at", "ts")} | post_event(body))


def run_hook(event: str, stdin_text: str) -> None:
    try:
        payload = json.loads(stdin_text or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
        {"stop": on_stop, "permission_request": on_permission_request}[event](payload)
    except Exception as exc:  # noqa: BLE001 - a hook must never break the Codex turn
        try:
            append_jsonl("hook-errors.jsonl", {"event": event, "error": type(exc).__name__, "ts": now_iso()})
        except OSError:
            pass
    print("{}")


# ---------------------------------------------------------------- reconcile

def reconcile(since: date | None) -> dict:
    root, state_path = sessions_dir(), state_dir() / "reconcile-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if since is None and state.get("last_run_date"):
        since = date.fromisoformat(state["last_run_date"]) - timedelta(days=1)  # overlap: late-finishing turns
    logged: dict[tuple, bool] = {}
    for r in read_jsonl(state_dir() / "turns.jsonl"):
        key = (r.get("session_id"), r.get("turn_id"))
        logged[key] = logged.get(key, False) or bool(r.get("wall_clock_exact"))
    report = {"since": since.isoformat() if since else None, "rollouts": 0, "turns": 0,
              "already_exact": 0, "filled_missing": 0, "upgraded_wall_clock": 0, "missing_by_day": {}}
    for path in sorted(root.rglob("*.jsonl")) if root.exists() else []:
        day = path_date(path, root)
        if since and (day or date.min) < since:
            continue
        report["rollouts"] += 1
        for t in turns_from_rollout(path).values():
            if not t["calls"]:
                continue
            report["turns"] += 1
            key = (t["session_id"], t["turn_id"])
            if logged.get(key):
                report["already_exact"] += 1
                continue
            if key in logged and not t["wall_clock_exact"]:
                continue  # still approximate; nothing better yet
            report["upgraded_wall_clock" if key in logged else "filled_missing"] += 1
            if key not in logged:
                bucket = day.isoformat() if day else "unknown"
                report["missing_by_day"][bucket] = report["missing_by_day"].get(bucket, 0) + 1
            if not t["wall_clock_exact"]:
                t["wall_clock_s"] = None  # turn never completed; don't guess from today's clock
            append_jsonl("turns.jsonl", {**t, "source": "reconcile", "ts": now_iso()})
            logged[key] = t["wall_clock_exact"]
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"last_run_date": date.today().isoformat(), "last_report": report}))
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    hook = sub.add_parser("hook", help="run as a Codex hook (reads the payload on stdin)")
    hook.add_argument("event", choices=["stop", "permission_request"])
    rec = sub.add_parser("reconcile", help="fill turn rows the hooks missed and report gaps")
    rec.add_argument("--since", type=date.fromisoformat, default=None, help="ISO date; default: day before last run")
    args = ap.parse_args(argv)
    if args.cmd == "hook":
        run_hook(args.event, sys.stdin.read())
    else:
        print(json.dumps(reconcile(args.since), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

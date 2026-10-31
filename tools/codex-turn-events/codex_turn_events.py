#!/usr/bin/env python3
"""Codex turn events: push turn_complete and needs_approval to a webhook.

  hook stop                 Codex Stop hook (async). POSTs turn_complete.
  hook permission_request   Codex PermissionRequest hook (async). POSTs needs_approval;
                            its wait_started_at starts the human-wait clock.

Tokens, cost and wall clock are not sent: join on (session_id, turn_id) with
tools/turn-cost-ledger, which is the one parser of Codex rollouts.

Webhook URL and key are read at run time from env vars
CODEX_EVENTS_WEBHOOK_URL / CODEX_EVENTS_WEBHOOK_KEY, else from the macOS
Keychain (generic passwords, services codex-events-webhook-url /
codex-events-webhook-key). They are never printed, logged or stored. The URL
must be https (http only for localhost / 127.0.0.1) and redirects are refused.
Hooks always print {} and exit 0. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PR_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
LOCAL_HOSTS = {"localhost", "127.0.0.1"}


def state_dir() -> Path:
    env = os.environ.get("CODEX_TURN_EVENTS_DIR")
    return Path(env).expanduser() if env else Path.home() / ".local" / "state" / "codex-turn-events"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_jsonl(name: str, row: dict) -> None:
    """Append to a 0600 file in a 0700 state dir (rows hold task names and PR URLs)."""
    root = state_dir()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    fd = os.open(root / name, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def url_allowed(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme == "https" and parts.hostname:
        return True
    return parts.scheme == "http" and parts.hostname in LOCAL_HOSTS


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect so the key is never re-sent to a Location host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def post_event(body: dict) -> dict:
    """POST body; return {posted, post_status|post_error}. Never includes URL or key."""
    url = secret("CODEX_EVENTS_WEBHOOK_URL", "codex-events-webhook-url")
    if not url:
        return {"posted": False, "post_error": "no webhook url configured"}
    if not url_allowed(url):
        return {"posted": False, "post_error": "invalid_url"}
    key = secret("CODEX_EVENTS_WEBHOOK_KEY", "codex-events-webhook-key")
    headers = {"Content-Type": "application/json", "User-Agent": "codex-turn-events/0.2"}
    if key:
        header = os.environ.get("CODEX_EVENTS_WEBHOOK_KEY_HEADER", "Authorization")
        headers[header] = f"Bearer {key}" if header.lower() == "authorization" else key
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=5) as resp:
            return {"posted": 200 <= resp.status < 300, "post_status": resp.status}
    except urllib.error.HTTPError as exc:  # includes every refused 3xx
        exc.close()
        return {"posted": False, "post_status": exc.code}
    except Exception as exc:  # noqa: BLE001 - report the class only; messages can carry the URL
        return {"posted": False, "post_error": type(exc).__name__}


# ---------------------------------------------------------------- hooks

def _common(payload: dict, event: str) -> dict:
    cwd = str(payload.get("cwd") or "")
    return {"source": "codex", "event": event, "session_id": str(payload.get("session_id") or ""),
            "turn_id": str(payload.get("turn_id") or ""), "task": Path(cwd).name if cwd else "",
            "model": str(payload.get("model") or "")}


def send(body: dict) -> None:
    result = post_event(body)
    append_jsonl("delivery.jsonl", {k: body[k] for k in ("event_id", "event", "ts")} | result)


def on_stop(payload: dict) -> None:
    body = _common(payload, "turn_complete")
    pr = PR_URL.findall(str(payload.get("last_assistant_message") or ""))
    body |= {"event_id": f"codex:{body['session_id']}:{body['turn_id']}:turn_complete",
             "status": "completed", "pr_url": pr[-1] if pr else None,
             "stop_hook_active": bool(payload.get("stop_hook_active")), "ts": now_iso()}
    send(body)


def on_permission_request(payload: dict) -> None:
    body = _common(payload, "needs_approval")
    tool_name = str(payload.get("tool_name") or "")
    # PermissionRequest has no tool_use_id; hash the request so a re-delivery dedupes
    # without sending the tool input itself.
    digest = hashlib.sha256(json.dumps([tool_name, payload.get("tool_input")], sort_keys=True,
                                       default=str).encode()).hexdigest()[:16]
    ts = now_iso()
    body |= {"event_id": f"codex:{body['session_id']}:{body['turn_id']}:needs_approval:{digest}",
             "status": "waiting_for_human", "tool_name": tool_name, "wait_started_at": ts, "ts": ts}
    send(body)


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    hook = sub.add_parser("hook", help="run as a Codex hook (reads the payload on stdin)")
    hook.add_argument("event", choices=["stop", "permission_request"])
    args = ap.parse_args(argv)
    run_hook(args.event, sys.stdin.read())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

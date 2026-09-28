#!/usr/bin/env python3
"""Record one usage row per Claude assistant API response at Stop."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from fsm_ledger.attribute import resolve_project
from fsm_ledger.ledger import append_dict
from fsm_ledger.render_trigger import schedule_render


def parse_stdin() -> dict:
    text = sys.stdin.read().strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def iter_transcript(path: Path):
    if not path.is_file():
        return
    try:
        with path.open(encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def main() -> int:
    payload = parse_stdin()
    cwd = str(payload.get("cwd") or os.environ.get("PWD") or "")
    session_id = str(payload.get("session_id") or "")
    transcript = payload.get("transcript_path") or payload.get("transcriptPath")
    if not transcript or not Path(str(transcript)).is_file():
        print("fsm-ledger Claude capture failed: transcript unavailable", file=sys.stderr)
    else:
        latest: dict[str, dict] = {}
        for row in iter_transcript(Path(str(transcript))):
            if row.get("type") != "assistant":
                continue
            message = row.get("message") or {}
            usage = message.get("usage") or row.get("usage") or {}
            msg_id = message.get("id") or row.get("message_id") or row.get("uuid")
            if msg_id and isinstance(usage, dict) and any(
                key in usage for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
            ):
                latest[str(msg_id)] = row
        for msg_id, row in latest.items():
            message = row.get("message") or {}
            usage = message.get("usage") or row.get("usage") or {}
            read = int(usage.get("cache_read_input_tokens") or usage.get("cached_input_tokens") or 0)
            write = int(usage.get("cache_creation_input_tokens") or 0)
            inp = int(usage.get("input_tokens") or 0) + read + write
            out = int(usage.get("output_tokens") or 0)
            event = {
                "event_id": f"claude:{session_id or Path(str(transcript)).stem}:{msg_id}",
                "harness": "claude", "model": str(message.get("model") or row.get("model") or ""),
                "inputTokens": inp, "outputTokens": out,
                "session_id": session_id, "cwd": cwd,
                "ts": row.get("timestamp"), "status": "response",
            }
            if "cache_read_input_tokens" in usage or "cached_input_tokens" in usage:
                event["cachedInputTokens"] = read
            if "cache_creation_input_tokens" in usage:
                event["cacheWriteInputTokens"] = write
            cost = usage.get("cost") or message.get("cost")
            if cost is not None:
                event["costTotal"] = cost
            result = append_dict(event)
            if not result.get("ok"):
                print(f"fsm-ledger Claude capture failed: {result.get('error')}", file=sys.stderr)

    try:
        schedule_render(resolve_project(cwd))
    except Exception:
        pass
    # Never block Claude on failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

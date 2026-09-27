#!/usr/bin/env python3
"""Claude Stop hook: parse session transcript JSONL for usage; dedupe by message UUID."""
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


def deep_find(data, candidates):
    wanted = set(candidates)
    if isinstance(data, dict):
        for k, v in data.items():
            if k in wanted:
                return v
            found = deep_find(v, wanted)
            if found is not None:
                return found
    elif isinstance(data, list):
        for v in data:
            found = deep_find(v, wanted)
            if found is not None:
                return found
    return None


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
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
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
    cwd = str(deep_find(payload, ["cwd"]) or os.environ.get("PWD") or "")
    session_id = str(deep_find(payload, ["session_id"]) or "")
    transcript = deep_find(payload, ["transcript_path", "transcriptPath"])
    appended = 0

    # Prefer direct usage on the Stop payload when present
    usage = deep_find(payload, ["usage", "token_usage"]) or {}
    if isinstance(usage, dict) and (usage.get("input_tokens") or usage.get("output_tokens")):
        row = {
            "harness": "claude",
            "model": str(deep_find(payload, ["model"]) or ""),
            "inputTokens": int(usage.get("input_tokens") or 0),
            "outputTokens": int(usage.get("output_tokens") or 0),
            "cachedInputTokens": int(usage.get("cache_read_input_tokens") or usage.get("cached_input_tokens") or 0),
            "session_id": session_id,
            "cwd": cwd,
            "message_id": str(deep_find(payload, ["message_id", "uuid"]) or ""),
            "status": "stop",
        }
        cost = usage.get("cost") or deep_find(payload, ["costTotal", "total_cost_usd"])
        if cost is not None:
            row["costTotal"] = float(cost)
        append_dict(row)
        appended += 1

    # Scan transcript JSONL — assistant messages with usage; dedupe by uuid
    if transcript:
        for row in iter_transcript(Path(str(transcript))):
            role = str(row.get("role") or row.get("type") or "").lower()
            if role not in ("assistant", "message"):
                # Claude Code JSONL often uses type=assistant
                if str(row.get("type") or "").lower() != "assistant":
                    continue
            msg_id = str(row.get("uuid") or row.get("id") or row.get("message_id") or "")
            usage = row.get("usage") or deep_find(row, ["usage"]) or {}
            if not isinstance(usage, dict):
                continue
            inp = int(usage.get("input_tokens") or 0)
            out = int(usage.get("output_tokens") or 0)
            if not inp and not out:
                continue
            event = {
                "harness": "claude",
                "model": str(deep_find(row, ["model"]) or ""),
                "inputTokens": inp,
                "outputTokens": out,
                "cachedInputTokens": int(
                    usage.get("cache_read_input_tokens") or usage.get("cached_input_tokens") or 0
                ),
                "session_id": session_id,
                "cwd": cwd,
                "message_id": msg_id,
                "status": "transcript",
            }
            cost = usage.get("cost") or deep_find(row, ["costTotal"])
            if cost is not None:
                try:
                    event["costTotal"] = float(cost)
                except (TypeError, ValueError):
                    pass
            append_dict(event)
            appended += 1

    try:
        schedule_render(resolve_project(cwd))
    except Exception:
        pass
    # Never block Claude on failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

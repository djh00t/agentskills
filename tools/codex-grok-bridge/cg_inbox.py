"""Build a read-only routing plan from Codex messages."""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import time
from pathlib import Path

import cg_envelope
import cg_log

NEEDS_DAVID = re.compile(r"\b(?:merge|deploy|I4|credential|key)\b", re.IGNORECASE)
ROLES = {"chief-of-staff": "", "peer-reviewer": ""}


def inbox(reader, log, conversation_id, limit=100, roles=None, roles_path=None, now=None):
    """Return unlogged Codex messages in sequence order."""
    cursor = log.cursor()
    recorded = {int(row["seq"]) for row in log._read()}
    messages = []
    while True:
        page = reader(conversation_id, cursor, limit)
        for message in page["messages"]:
            if message.get("sender") != "codex":
                continue
            seq = int(message["seq"])
            if seq in recorded:
                continue
            parsed = cg_envelope.parse(message["text"], roles_path)
            role = parsed["to"]
            body = parsed["body"]
            expiry = message.get("expires_at")
            entry = {"seq": seq, "message_id": message["id"], "req_id": parsed["req"],
                     "kind": parsed["kind"], "route_to_role": role,
                     "route_to_agent_id": (roles or ROLES).get(role) if role else None,
                     "needs_david": parsed["kind"] == "decision" or bool(NEEDS_DAVID.search(body)),
                     "excerpt": body[:200]}
            if expiry is not None and (now if now is not None else time.time()) >= expiry:
                entry["expired"] = True
            messages.append(entry)
        next_cursor = page["next_cursor"]
        if next_cursor is None or next_cursor == cursor:
            break
        cursor = next_cursor
    return sorted(messages, key=lambda item: item["seq"])


def _reader(spec):
    module_name, attribute = spec.split(":", 1)
    return getattr(importlib.import_module(module_name), attribute)


def main(argv=None, reader=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("conversation_id")
    parser.add_argument("--reader", help="importable module:callable")
    parser.add_argument("--log", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--roles", help="JSON file mapping roles to agent IDs")
    args = parser.parse_args(argv)
    try:
        reader = reader or _reader(args.reader)
        roles = json.loads(Path(args.roles).read_text()) if args.roles else ROLES
        print(json.dumps(inbox(reader, cg_log.MessageLog(args.log), args.conversation_id,
                               args.limit, roles, args.roles)))
    except Exception as error:
        print(f"cg_inbox: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

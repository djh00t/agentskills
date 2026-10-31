"""Compose dry-run ACK and RESULT message_send arguments.

The command prints JSON only. It never sends a message. Use --confirm with the
returned message ID to mark the logged inbound message as acked.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from cg_envelope import MAX_BYTES, format_envelope
from cg_log import MessageLog

MAX_OUTPUT_BYTES = 16_384
TRUNCATION_MARKER = "[summary truncated]"
FORBIDDEN = re.compile(r"(?:\bapproved\s+by\b|\bapproval\b|\bcard\s*#)", re.I)


class ReplyError(ValueError):
    """Invalid reply input or confirmation."""


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def compose(*, kind: str, req: str, role: str, re_seq: str, reply_to: str,
            summary: str, artifacts: list[str] | None = None, usage: dict | None = None,
            routed_at: datetime | None = None) -> dict:
    """Build deterministic message_send arguments without sending them."""
    if kind not in {"ack", "result"}:
        raise ReplyError("kind must be ack or result")
    if not isinstance(reply_to, str) or not reply_to:
        raise ReplyError("reply_to message ID is required")
    if not isinstance(summary, str):
        raise ReplyError("summary must be text")
    if FORBIDDEN.search(summary):
        raise ReplyError("approval and card references are not allowed")
    when = routed_at or datetime.now(ZoneInfo("Australia/Sydney"))
    when = when.astimezone(ZoneInfo("Australia/Sydney"))
    if kind == "ack":
        body = f"routed to {role} at {when:%Y-%m-%d %H:%M:%S %Z}; state {summary}"
    else:
        body = summary
        if artifacts:
            body += "\nArtifacts:\n" + "\n".join(artifacts)
        if usage is not None:
            if not isinstance(usage, dict):
                raise ReplyError("usage must be a JSON object")
            body += "\nUsage:\n" + json.dumps(usage, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def arguments(text: str) -> dict:
        envelope = format_envelope(req, kind, role, re_seq, text)
        return {"reply_to": reply_to, "message": envelope}

    try:
        result = arguments(body)
        if len(_json_bytes(result)) <= MAX_OUTPUT_BYTES:
            return result
    except ValueError as error:
        if kind != "result" or "exceeds" not in str(error):
            raise
    if kind != "result":
        raise ReplyError("ACK exceeds output limit")
    fixed = body[len(summary):]
    available = MAX_BYTES - len(f"[CG req={req} kind=result to={role} re={re_seq}]\n".encode()) - len(fixed.encode())
    raw = summary.encode("utf-8")
    marker = ("\n" + TRUNCATION_MARKER).encode()
    limit = max(0, available - len(marker))
    truncated = raw[:limit].decode("utf-8", errors="ignore") + "\n" + TRUNCATION_MARKER
    result = arguments(truncated + fixed)
    output = _json_bytes(result)
    if len(output) > MAX_OUTPUT_BYTES:
        excess = len(output) - MAX_OUTPUT_BYTES
        truncated = truncated[:-len(TRUNCATION_MARKER) - 1 - excess]
        result = arguments(truncated + "\n" + TRUNCATION_MARKER + fixed)
    if len(_json_bytes(result)) > MAX_OUTPUT_BYTES:
        raise ReplyError("fixed RESULT fields exceed output limit")
    return result


def confirm(log_path: str | Path, seq: int, message_id: str | None) -> None:
    """Mark an inbound row acked only after a returned message ID is supplied."""
    if message_id is None:
        raise ReplyError("--confirm requires a returned message ID")
    if not message_id.strip():
        raise ReplyError("message ID must not be empty")
    MessageLog(log_path).transition(seq, "acked", ack_msg_id=message_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("ack", "result"))
    parser.add_argument("--req")
    parser.add_argument("--role")
    parser.add_argument("--re", dest="re_seq", default="-")
    parser.add_argument("--reply-to")
    parser.add_argument("--summary")
    parser.add_argument("--artifacts", default="[]", help="JSON array of artifact paths or PR links")
    parser.add_argument("--usage", help="optional JSON usage object")
    parser.add_argument("--log")
    parser.add_argument("--seq", type=int)
    parser.add_argument("--confirm", metavar="MSG_ID")
    args = parser.parse_args(argv)
    try:
        if args.confirm is not None or (args.log and args.seq is not None and args.kind is None):
            if not args.log or args.seq is None:
                raise ReplyError("--confirm requires --log and --seq")
            confirm(args.log, args.seq, args.confirm)
            return 0
        if not all((args.kind, args.req, args.role, args.reply_to, args.summary is not None)):
            raise ReplyError("composition requires --kind, --req, --role, --reply-to, and --summary")
        artifacts = json.loads(args.artifacts)
        usage = json.loads(args.usage) if args.usage else None
        if not isinstance(artifacts, list) or any(not isinstance(item, str) for item in artifacts):
            raise ReplyError("artifacts must be a JSON array of strings")
        print(_json_bytes(compose(kind=args.kind, req=args.req, role=args.role, re_seq=args.re_seq,
                                  reply_to=args.reply_to, summary=args.summary, artifacts=artifacts,
                                  usage=usage)).decode(), end="")
    except (ReplyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

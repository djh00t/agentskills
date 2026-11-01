"""Build a read-only routing plan from Codex messages."""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import time

import cg_envelope
import cg_log

NEEDS_OWNER = re.compile(
    r"\b(?:merg(?:e|es|ed|ing)|deploy\w*|release\w*|I4|credentials?|keys?|secrets?|tokens?|passwords?|approv\w*)\b",
    re.IGNORECASE,
)


class InboxError(ValueError):
    """The reader input violates the inbox contract."""


def inbox(reader, log, conversation_id, limit=100, roles_path=None, now=None, max_pages=1000):
    """Return new and received-but-unrouted Codex messages in sequence order."""
    if type(limit) is not int or limit < 1 or type(max_pages) is not int or max_pages < 1:
        raise InboxError("limit and max_pages must be positive integers")
    roles = cg_envelope.load_roles(roles_path) if roles_path is not None else {}
    cursor, seqs = log.snapshot()
    handled_cursor = cursor
    pending = log.pending_sequences()
    now = time.time() if now is None else now
    seen_seqs = set()
    seen_tokens = {cursor}
    messages = []
    for page_number in range(max_pages):
        page = reader(conversation_id, cursor, limit)
        if not isinstance(page, dict) or not isinstance(page.get("messages"), list) or "next_cursor" not in page:
            raise InboxError("reader returned an invalid page")
        for message in page["messages"]:
            if isinstance(message, dict) and message.get("sender") != "codex":
                continue
            seq = message.get("seq") if isinstance(message, dict) else None
            message_id = message.get("id") if isinstance(message, dict) else None
            valid_seq = isinstance(seq, int) and not isinstance(seq, bool) and seq >= 0
            valid_id = isinstance(message_id, str) and bool(message_id)
            try:
                if not isinstance(message, dict) or not valid_seq or not valid_id:
                    raise InboxError("message needs a non-negative integer seq and non-empty string id")
                if seq in seen_seqs:
                    continue
                seen_seqs.add(seq)
                if seq not in pending and (seq in seqs or (seqs and seq <= handled_cursor and handled_cursor >= min(seqs))):
                    continue
                parsed = cg_envelope.parse(message.get("text"), roles=roles)
                expiry = message.get("expires_at")
                if expiry is not None and (
                    isinstance(expiry, bool) or not isinstance(expiry, (int, float))
                    or not 0 <= expiry <= 253402300799
                ):
                    raise InboxError("expires_at must be finite epoch seconds in years 1970 through 9999")
                role = parsed["to"]
                messages.append({
                    "seq": seq, "message_id": message_id, "req_id": parsed["req"],
                    "kind": parsed["kind"], "route_to_role": role,
                    "route_to_agent_id": roles[role] if role else None,
                    "needs_owner": parsed["kind"] == "decision" or bool(parsed["warnings"])
                                   or bool(NEEDS_OWNER.search(message["text"])),
                    "warnings": parsed["warnings"], "execution_authorized": False,
                    "excerpt": parsed["body"][:200], "pending": seq in pending,
                    "expired": expiry is not None and now >= expiry,
                })
            except (InboxError, cg_envelope.EnvelopeError) as error:
                messages.append({"seq": seq if valid_seq else None,
                                 "message_id": message_id if valid_id else None,
                                 "error": str(error), "needs_owner": True,
                                 "expired": False, "execution_authorized": False})
        next_cursor = page["next_cursor"]
        if next_cursor is None:
            break
        if isinstance(next_cursor, bool) or not isinstance(next_cursor, (str, int)):
            raise InboxError("reader returned an invalid page token")
        if next_cursor in seen_tokens:
            break
        if page_number + 1 == max_pages:
            raise InboxError("too many pages")
        seen_tokens.add(next_cursor)
        cursor = next_cursor
    return sorted(messages, key=lambda item: (item["seq"] is None, item["seq"] or 0))


def _reader(spec):
    module_name, _, attribute = spec.partition(":")
    reader = getattr(importlib.import_module(module_name), attribute)
    if not callable(reader):
        raise InboxError("--reader must name a callable")
    return reader


def _positive(value):
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv=None, reader=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("conversation_id")
    parser.add_argument("--reader", required=reader is None, help="read-only importable module:callable")
    parser.add_argument("--log", required=True)
    parser.add_argument("--legacy", help="legacy last-sequence file")
    parser.add_argument("--limit", type=_positive, default=100)
    parser.add_argument("--roles", help="optional JSON file mapping roles to agent IDs")
    args = parser.parse_args(argv)
    if args.reader is not None:
        module, sep, attribute = args.reader.partition(":")
        if not (module and sep and attribute) or ":" in attribute:
            parser.error("--reader must be module:callable")
    try:
        reader = reader if reader is not None else _reader(args.reader)
        print(json.dumps(inbox(reader, cg_log.MessageLog(args.log, args.legacy),
                               args.conversation_id, args.limit, args.roles)))
    except (OSError, ValueError, ImportError, AttributeError) as error:
        print(f"cg_inbox: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

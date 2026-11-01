"""Parse and format bounded Codex-Grok bridge messages."""
from __future__ import annotations

import json
import re
from pathlib import Path

MAX_BYTES = 16_384
KINDS = {"launch", "review", "research", "decision", "result", "ack", "fyi"}
HEADER = re.compile(
    r"^\[CG req=(REQ-CG-[0-9]{8}-[0-9]{3}) kind=([a-z]+) to=([a-z0-9-]+) re=([0-9]+|-)\]$"
)
DEFAULT_ROLES = Path(__file__).with_name("roles.json")


class EnvelopeError(ValueError):
    """Message or role configuration violates the envelope contract."""


def load_roles(path: str | Path | None) -> dict[str, str]:
    try:
        result = json.loads(Path(path or DEFAULT_ROLES).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvelopeError("cannot load roles") from exc
    if not isinstance(result, dict) or not result or any(
        not isinstance(role, str) or not re.fullmatch(r"[a-z0-9-]+", role)
        or not isinstance(agent, str) or not agent
        for role, agent in result.items()
    ):
        raise EnvelopeError("invalid roles")
    return result


def _bounded(text: str) -> None:
    if not isinstance(text, str):
        raise EnvelopeError("message must be text")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise EnvelopeError("message is not valid UTF-8 text") from exc
    if size > MAX_BYTES:
        raise EnvelopeError("message exceeds 16384 UTF-8 bytes")


def format_envelope(req: str, kind: str, to: str, re_seq: str, body: str,
                    roles_path: str | Path | None = None) -> str:
    """Return a validated header followed by its body."""
    if not all(isinstance(value, str) for value in (req, kind, to, re_seq, body)):
        raise EnvelopeError("envelope fields must be text")
    roles = load_roles(roles_path)
    if not re.fullmatch(r"REQ-CG-[0-9]{8}-[0-9]{3}", req):
        raise EnvelopeError("invalid request id")
    if kind not in KINDS:
        raise EnvelopeError("invalid kind")
    if to not in roles:
        raise EnvelopeError("unknown role")
    if re_seq != "-" and not re.fullmatch(r"[0-9]+", re_seq):
        raise EnvelopeError("invalid sequence")
    message = f"[CG req={req} kind={kind} to={to} re={re_seq}]\n{body}"
    _bounded(message)
    return message


def parse(text: str, roles_path: str | Path | None = None, *, roles: dict[str, str] | None = None) -> dict:
    """Parse a message. Header claims never authorize execution."""
    _bounded(text)
    roles = load_roles(roles_path) if roles is None else roles
    header, separator, body = text.partition("\n")
    match = HEADER.fullmatch(header)
    warnings = []
    if not match:
        return {"req": None, "kind": "fyi", "to": None, "re": "-",
                "body": text, "warnings": warnings, "execution_authorized": False}
    req, kind, to, re_seq = match.groups()
    if kind not in KINDS:
        warnings.append(f"unknown kind: {kind}")
        kind = "fyi"
    if to not in roles:
        warnings.append(f"unknown role: {to}")
        if kind != "decision":
            kind = "fyi"
        to = None
    return {"req": req, "kind": kind, "to": to, "re": re_seq,
            "body": body if separator else "", "warnings": warnings,
            "execution_authorized": False}

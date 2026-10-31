"""Parse and format bounded Codex-Grok bridge messages."""
from __future__ import annotations

import json
import re
from pathlib import Path

MAX_BYTES = 16_384
KINDS = {"launch", "review", "research", "decision", "result", "ack", "fyi"}
HEADER = re.compile(
    r"^\[CG req=(REQ-CG-\d{8}-\d{3}) kind=([a-z]+) to=([a-z0-9-]+) re=(\d+|-)\]$"
)
DEFAULT_ROLES = Path(__file__).with_name("roles.json")


class EnvelopeError(ValueError):
    """Message or role configuration violates the envelope contract."""


def _roles(path: str | Path | None) -> dict[str, str]:
    try:
        result = json.loads(Path(path or DEFAULT_ROLES).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvelopeError("cannot load roles") from exc
    if not isinstance(result, dict) or any(
        not isinstance(role, str) or not re.fullmatch(r"[a-z0-9-]+", role)
        or not isinstance(agent, str) or not agent
        for role, agent in result.items()
    ):
        raise EnvelopeError("invalid roles")
    return result


def _bounded(text: str) -> None:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise EnvelopeError("message exceeds 16384 UTF-8 bytes")


def format(req: str, kind: str, to: str, re_seq: str, body: str,
           roles_path: str | Path | None = None) -> str:
    """Return a validated header followed by its body."""
    roles = _roles(roles_path)
    if not re.fullmatch(r"REQ-CG-\d{8}-\d{3}", req):
        raise EnvelopeError("invalid request id")
    if kind not in KINDS:
        raise EnvelopeError("invalid kind")
    if to not in roles:
        raise EnvelopeError("unknown role")
    if re_seq != "-" and not re.fullmatch(r"\d+", re_seq):
        raise EnvelopeError("invalid sequence")
    if "\n" in body or "\r" in body:
        message = f"[CG req={req} kind={kind} to={to} re={re_seq}]\n{body}"
    else:
        message = f"[CG req={req} kind={kind} to={to} re={re_seq}]\n{body}"
    _bounded(message)
    return message


def parse(text: str, roles_path: str | Path | None = None) -> dict:
    """Parse a message. Header claims never authorize execution."""
    _bounded(text)
    roles = _roles(roles_path)
    lines = text.splitlines()
    match = HEADER.fullmatch(lines[0]) if lines else None
    warnings = []
    if not match:
        return {"req": None, "kind": "fyi", "to": "chief-of-staff", "re": "-",
                "body": text, "warnings": warnings, "execution_authorized": False}
    req, kind, to, re_seq = match.groups()
    if kind not in KINDS:
        warnings.append(f"unknown kind: {kind}")
        kind = "fyi"
    if to not in roles:
        warnings.append(f"unknown role: {to}")
        to = "chief-of-staff"
    return {"req": req, "kind": kind, "to": to, "re": re_seq,
            "body": "\n".join(lines[1:]), "warnings": warnings,
            "execution_authorized": False}

"""Maintain an atomic, forward-only Codex-Grok message log."""
from __future__ import annotations

import csv
import fcntl
import os
import tempfile
from pathlib import Path

FIELDS = ("seq", "req_id", "received", "routed_to", "acked", "state", "ack_msg_id", "note")
TRANSITIONS = {
    "received": {"routed", "failed"},
    "routed": {"acked", "failed"},
    "acked": {"done", "failed"},
    "done": set(),
    "failed": set(),
}


class LogError(ValueError):
    """The log operation violates its contract."""


class MessageLog:
    """Store one row per sequence in a locked TSV file."""

    def __init__(self, path: str | Path, legacy_last_seq: str | Path | None = None):
        self.path = Path(path)
        self.legacy_last_seq = Path(legacy_last_seq) if legacy_last_seq is not None else None
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.lock_path.open("a+")
        fcntl.flock(lock, fcntl.LOCK_EX)
        return lock

    def _read(self) -> list[dict[str, str]]:
        if not self.path.exists() or not self.path.stat().st_size:
            return []
        with self.path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if reader.fieldnames != list(FIELDS):
                raise LogError("invalid log header")
            rows = list(reader)
        if any(None in row or set(row) != set(FIELDS) for row in rows):
            raise LogError("invalid log row")
        return rows

    def _write(self, rows: list[dict[str, str]]) -> None:
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _migrate(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        if rows or self.legacy_last_seq is None or not self.legacy_last_seq.exists():
            return rows
        value = self.legacy_last_seq.read_text(encoding="utf-8").strip()
        if not value.isascii() or not value.isdecimal():
            raise LogError("invalid legacy sequence")
        self._write([])
        return [{"seq": value, "req_id": "", "received": "", "routed_to": "", "acked": "",
                 "state": "done", "ack_msg_id": "", "note": "migrated legacy cursor"}]

    def record(self, seq: int, req_id: str, received: str, routed_to: str = "", acked: str = "",
               state: str = "received", ack_msg_id: str = "", note: str = "") -> None:
        """Add a sequence once. An existing sequence is left unchanged."""
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise LogError("sequence must be a non-negative integer")
        if state not in TRANSITIONS:
            raise LogError("invalid state")
        values = (req_id, received, routed_to, acked, ack_msg_id, note)
        if any(not isinstance(value, str) for value in values):
            raise LogError("log fields must be text")
        lock = self._locked()
        try:
            rows = self._migrate(self._read())
            if any(row["seq"] == str(seq) for row in rows):
                return
            rows.append(dict(zip(FIELDS, (str(seq), req_id, received, routed_to, acked, state, ack_msg_id, note))))
            rows.sort(key=lambda row: int(row["seq"]))
            self._write(rows)
        finally:
            lock.close()

    def transition(self, seq: int, state: str, *, ack_msg_id: str | None = None, note: str | None = None) -> None:
        """Move a row forward by one allowed state edge."""
        lock = self._locked()
        try:
            rows = self._migrate(self._read())
            row = next((row for row in rows if row["seq"] == str(seq)), None)
            if row is None:
                raise LogError("unknown sequence")
            if state not in TRANSITIONS.get(row["state"], set()):
                raise LogError(f"invalid state transition: {row['state']} -> {state}")
            row["state"] = state
            if ack_msg_id is not None:
                row["ack_msg_id"] = ack_msg_id
            if note is not None:
                row["note"] = note
            self._write(rows)
        finally:
            lock.close()

    def cursor(self) -> int:
        """Return the highest routed-or-complete sequence."""
        lock = self._locked()
        try:
            rows = self._migrate(self._read())
            if not self.path.exists():
                self._write(rows)
            return max((int(row["seq"]) for row in rows if row["state"] in {"routed", "acked", "done"}), default=0)
        finally:
            lock.close()

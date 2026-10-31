"""Maintain an atomic, forward-only Codex-Grok message log."""
from __future__ import annotations

import csv
import fcntl
import os
import tempfile
from pathlib import Path

FIELDS = ("seq", "req_id", "received_at", "routed_to", "acked", "state", "ack_msg_id", "note")
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
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        lock = os.fdopen(fd, "a+")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
        except BaseException:
            lock.close()
            raise
        return lock

    def _read(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        try:
            with self.path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream, delimiter="\t", strict=True)
                if reader.fieldnames != list(FIELDS):
                    raise LogError("invalid log header")
                rows = list(reader)
        except (csv.Error, UnicodeError) as error:
            raise LogError("invalid log encoding or TSV") from error
        seen = set()
        for row in rows:
            if None in row or any(value is None for value in row.values()):
                raise LogError("invalid log row")
            value = row["seq"]
            if not value.isascii() or not value.isdecimal():
                raise LogError("invalid log sequence")
            try:
                seq = int(value)
            except ValueError as error:
                raise LogError("invalid log sequence") from error
            if seq in seen:
                raise LogError("duplicate log sequence")
            if row["state"] not in TRANSITIONS:
                raise LogError("invalid log state")
            seen.add(seq)
            row["seq"] = str(seq)
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
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _migrate(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        if (self.legacy_last_seq is None or not self.legacy_last_seq.exists()
                or any(row["note"] == "migrated legacy cursor" and row["state"] == "done"
                       and not row["req_id"] for row in rows)):
            return rows
        try:
            value = self.legacy_last_seq.read_text(encoding="utf-8-sig").strip()
            legacy = int(value) if value.isascii() and value.isdecimal() else None
        except ValueError as error:
            raise LogError("invalid legacy sequence") from error
        if legacy is None:
            raise LogError("invalid legacy sequence")
        if self.path.exists():
            if legacy > self._cursor(rows):
                raise LogError("legacy sequence is higher than existing cursor")
            return rows
        return [{"seq": str(legacy), "req_id": "", "received_at": "", "routed_to": "", "acked": "",
                 "state": "done", "ack_msg_id": "", "note": "migrated legacy cursor"}]

    def record(self, seq: int, req_id: str, received_at: str, routed_to: str = "", acked: str = "",
               state: str = "received", ack_msg_id: str = "", note: str = "") -> None:
        """Add a sequence once; reject new rows below a handled cursor."""
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise LogError("sequence must be a non-negative integer")
        if state != "received":
            raise LogError("initial state must be received")
        values = (req_id, received_at, routed_to, acked, ack_msg_id, note)
        if any(not isinstance(value, str) for value in values):
            raise LogError("log fields must be text")
        if note == "migrated legacy cursor":
            raise LogError("reserved migration note")
        lock = self._locked()
        try:
            original = self._read()
            rows = self._migrate(original)
            if any(row["seq"] == str(seq) for row in rows):
                return
            cursor = self._cursor(rows)
            if rows and seq <= cursor and cursor >= min(int(row["seq"]) for row in rows):
                raise LogError("sequence must be above the current cursor")
            rows.append(dict(zip(FIELDS, (str(seq), req_id, received_at, routed_to, acked, state, ack_msg_id, note))))
            rows.sort(key=lambda row: int(row["seq"]))
            self._write(rows)
        finally:
            lock.close()

    def transition(self, seq: int, state: str, *, ack_msg_id: str | None = None, note: str | None = None) -> None:
        """Move a row forward by one allowed state edge."""
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise LogError("sequence must be a non-negative integer")
        if not isinstance(state, str) or state not in TRANSITIONS:
            raise LogError("invalid state")
        if any(value is not None and not isinstance(value, str) for value in (ack_msg_id, note)):
            raise LogError("log fields must be text")
        if note == "migrated legacy cursor":
            raise LogError("reserved migration note")
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

    @staticmethod
    def _cursor(rows: list[dict[str, str]]) -> int:
        ordered = sorted(rows, key=lambda row: int(row["seq"]))
        cursor = max(0, int(ordered[0]["seq"]) - 1) if ordered else 0
        for row in ordered:
            seq = int(row["seq"])
            if seq > cursor + 1 or row["state"] not in {"routed", "acked", "done", "failed"}:
                break
            cursor = seq
        return cursor

    def cursor(self) -> int:
        """Return the contiguous handled cursor; persist a legacy seed once."""
        lock = self._locked()
        try:
            original = self._read()
            rows = self._migrate(original)
            if rows != original:
                self._write(rows)
            return self._cursor(rows)
        finally:
            lock.close()

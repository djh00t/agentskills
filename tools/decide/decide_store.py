"""Append-only, hash-chained event storage for decide."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat

from decide_common import DecideError, EXIT_CONFLICT, EXIT_ENV, emit, home_dir, iso_z, utc_now


ZERO_HASH = "0" * 64


class Store:
    def __init__(self, home: Path):
        self.home = Path(home)
        try:
            mode = self.home.stat().st_mode
        except FileNotFoundError:
            raise DecideError(EXIT_ENV, "home dir missing")
        if not self.home.is_dir():
            raise DecideError(EXIT_ENV, "home dir missing")
        if stat.S_IMODE(mode) & 0o077:
            raise DecideError(EXIT_ENV, "home dir must not be group or world accessible")
        self.path = self.home / "events.jsonl"
        self.lock_path = self.home / ".lock"
        self._locked = False

    def lock(self):
        return _StoreLock(self)

    def read_events(self):
        if not self.path.exists():
            return []
        events = []
        with self.path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    raise DecideError(EXIT_ENV, "events.jsonl line {} is not JSON".format(number))
        return events

    def last_line_bytes(self):
        try:
            content = self.path.read_bytes()
        except FileNotFoundError:
            return None
        lines = [line for line in content.splitlines() if line]
        return lines[-1] if lines else None

    def append(self, event_type, item_id, data):
        if not self._locked:
            raise RuntimeError("append requires the store lock")
        events = self.read_events()
        previous = self.last_line_bytes()
        event = {
            "seq": events[-1]["seq"] + 1 if events else 1,
            "ts": iso_z(utc_now()),
            "type": event_type,
            "id": item_id,
            "data": data,
            "prev_sha256": hashlib.sha256(previous).hexdigest() if previous is not None else ZERO_HASH,
        }
        line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        fd = os.open(str(self.path), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "ab") as stream:
            stream.write(line + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event

    def verify(self):
        self.read_events()
        try:
            content = self.path.read_bytes()
        except FileNotFoundError:
            content = b""
        lines = [line for line in content.splitlines() if line]
        previous = ZERO_HASH
        previous_seq = 0
        for number, raw in enumerate(lines, 1):
            event = json.loads(raw)
            seq = event.get("seq")
            if event.get("prev_sha256") != previous:
                return _broken(len(lines), seq, "prev_sha256 mismatch")
            if seq != previous_seq + 1:
                return _broken(len(lines), seq, "seq gap")
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if raw != canonical:
                return _broken(len(lines), seq, "not canonical")
            previous = hashlib.sha256(raw).hexdigest()
            previous_seq = seq
        return {"ok": True, "events": len(lines), "bad_seq": None, "reason": None}


class _StoreLock:
    def __init__(self, store):
        self.store = store
        self.fd = None

    def __enter__(self):
        self.fd = os.open(str(self.store.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.store._locked = True
        return self.store

    def __exit__(self, exc_type, exc_value, traceback):
        self.store._locked = False
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


def _broken(count, seq, reason):
    return {"ok": False, "events": count, "bad_seq": seq, "reason": reason}


def _verify_log(args):
    result = Store(home_dir(args)).verify()
    emit(args, result, "ok: {} events".format(result["events"]) if result["ok"] else
         "broken at seq {}: {}".format(result["bad_seq"], result["reason"]))
    return 0 if result["ok"] else EXIT_CONFLICT


def register(subparsers):
    command = subparsers.add_parser("verify-log")
    command.set_defaults(func=_verify_log)

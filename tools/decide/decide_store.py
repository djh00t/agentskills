"""Append-only, hash-chained event storage for decide."""

import fcntl
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import stat
import threading
import tempfile

from decide_common import DecideError, EXIT_CONFLICT, EXIT_ENV, emit, home_dir, iso_z, utc_now

ZERO_HASH = "0" * 64
MAX_LINE_BYTES = 1024 * 1024
KEYS = {"seq", "ts", "type", "id", "data", "prev_sha256"}


def _secure_open(path, flags):
    try:
        fd = os.open(str(path), flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    except OSError as exc:
        if isinstance(exc, FileNotFoundError):
            raise
        raise DecideError(EXIT_ENV, "cannot open store file safely") from exc
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise DecideError(EXIT_ENV, "store file must be private and owned by the current user")
    os.set_blocking(fd, True)
    return fd


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Store:
    def __init__(self, home: Path):
        self.home = Path(home)
        try:
            info = self.home.lstat()
        except FileNotFoundError:
            raise DecideError(EXIT_ENV, "home dir missing")
        if not stat.S_ISDIR(info.st_mode):
            raise DecideError(EXIT_ENV, "home dir missing")
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise DecideError(EXIT_ENV, "home dir must be private and owned by the current user")
        self.path = self.home / "events.jsonl"
        self.lock_path = self.home / ".lock"
        self.head_path = self.home / "head"
        self._owner = None
        self._holders = set()

    def lock(self, shared=False):
        return _StoreLock(self, shared)

    def _read(self, path):
        try:
            fd = _secure_open(path, os.O_RDONLY)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, "rb") as stream:
            return stream.read()

    def append(self, event_type, item_id, data):
        if self._owner != threading.get_ident():
            raise RuntimeError("append requires the store lock")
        result, lines = self._verify_locked()
        if result["reason"] == "head mismatch" and lines:
            previous_hash = hashlib.sha256(lines[-2]).hexdigest() if len(lines) > 1 else ZERO_HASH
            prior_head = json.dumps({"seq": len(lines) - 1, "sha256": previous_hash},
                                    sort_keys=True, separators=(",", ":")).encode()
            if self._read(self.head_path) == prior_head:
                self._write_head(len(lines), hashlib.sha256(lines[-1]).hexdigest())
                result = {"ok": True}
        if not result["ok"]:
            raise DecideError(EXIT_CONFLICT, "cannot append to a broken log", result)
        previous = lines[-1] if lines else None
        event = {"seq": len(lines) + 1, "ts": iso_z(utc_now()), "type": event_type,
                 "id": item_id, "data": data,
                 "prev_sha256": hashlib.sha256(previous).hexdigest() if previous else ZERO_HASH}
        line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(line) > MAX_LINE_BYTES:
            raise DecideError(EXIT_CONFLICT, "event exceeds size limit")
        try:
            fd = _secure_open(self.path, os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_WRONLY)
            created = True
        except DecideError as exc:
            if not isinstance(exc.__cause__, FileExistsError):
                raise
            fd = _secure_open(self.path, os.O_APPEND | os.O_WRONLY)
            created = False
        with os.fdopen(fd, "ab") as stream:
            stream.write(line + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        if created:
            _sync_dir(self.home)
        self._write_head(event["seq"], hashlib.sha256(line).hexdigest())
        return event

    def _write_head(self, seq, digest):
        head = json.dumps({"seq": seq, "sha256": digest},
                          sort_keys=True, separators=(",", ":")).encode()
        fd, name = tempfile.mkstemp(prefix=".head-", dir=self.home)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(head)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.head_path)
            _sync_dir(self.home)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def verify(self):
        with self.lock(shared=True):
            return self._verify_locked()[0]

    def _verify_locked(self):
        content = self._read(self.path) or b""
        lines = content.splitlines()
        previous = ZERO_HASH
        for number, raw in enumerate(lines, 1):
            if len(raw) > MAX_LINE_BYTES:
                return _broken(len(lines), number, "line exceeds size limit"), lines
            try:
                event = json.loads(raw)
            except (ValueError, UnicodeDecodeError, RecursionError):
                return _broken(len(lines), number, "not JSON"), lines
            seq = event.get("seq") if isinstance(event, dict) else None
            if not isinstance(event, dict) or set(event) != KEYS:
                return _broken(len(lines), number, "invalid event shape"), lines
            if type(seq) is not int:
                return _broken(len(lines), number, "invalid event shape"), lines
            try:
                timestamp = datetime.strptime(event["ts"], "%Y-%m-%dT%H:%M:%SZ")
                valid_time = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") == event["ts"]
            except (ValueError, TypeError):
                valid_time = False
            if not valid_time or not isinstance(event["type"], str) or not event["type"]:
                return _broken(len(lines), number, "invalid event shape"), lines
            if event["prev_sha256"] != previous:
                return _broken(len(lines), seq, "prev_sha256 mismatch"), lines
            if seq != number:
                return _broken(len(lines), seq, "seq gap"), lines
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if raw != canonical:
                return _broken(len(lines), seq, "not canonical"), lines
            previous = hashlib.sha256(raw).hexdigest()
        if content and not content.endswith(b"\n"):
            return _broken(len(lines), len(lines), "incomplete line"), lines
        head = self._read(self.head_path)
        expected = json.dumps({"seq": len(lines), "sha256": previous}, sort_keys=True, separators=(",", ":")).encode()
        if (lines or head is not None) and head != expected:
            return _broken(len(lines), len(lines), "head mismatch"), lines
        return {"ok": True, "events": len(lines), "bad_seq": None, "reason": None}, lines


class _StoreLock:
    def __init__(self, store, shared):
        self.store = store
        self.shared = shared
        self.fd = None

    def __enter__(self):
        if threading.get_ident() in self.store._holders:
            raise RuntimeError("store lock is not reentrant")
        self.fd = _secure_open(self.store.lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(self.fd, fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX)
        self.store._holders.add(threading.get_ident())
        if not self.shared:
            self.store._owner = threading.get_ident()
        return self.store

    def __exit__(self, exc_type, exc_value, traceback):
        self.store._holders.remove(threading.get_ident())
        if not self.shared:
            self.store._owner = None
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

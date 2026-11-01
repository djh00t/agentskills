"""Derived SQLite index for item reads."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing

from decide_common import DecideError, EXIT_CONFLICT, emit, home_dir


ZERO_HASH = "0" * 64


def _log_head(store):
    content = store._read(store.path) or b""
    lines = content.splitlines()
    if not lines:
        return 0, ZERO_HASH
    return len(lines), hashlib.sha256(lines[-1]).hexdigest()


def _database(store):
    path = store.home / "decide.db"
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    return path


def _replace_locked(store):
    from decide_state import fold

    result, lines = store._verify_locked()
    if not result["ok"]:
        raise DecideError(EXIT_CONFLICT, "cannot index a broken log", result)
    events = [json.loads(line) for line in lines]
    all_items = fold(events)
    last_seq = len(lines)
    last_hash = hashlib.sha256(lines[-1]).hexdigest() if lines else ZERO_HASH
    path = _database(store)
    with closing(sqlite3.connect(path)) as db:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, state TEXT, kind TEXT, priority TEXT, requester TEXT, json TEXT)")
            db.execute("DELETE FROM meta")
            db.execute("DELETE FROM items")
            db.executemany("INSERT INTO meta(k, v) VALUES (?, ?)",
                           (("last_seq", str(last_seq)), ("last_sha256", last_hash)))
            db.executemany(
                "INSERT INTO items(id, state, kind, priority, requester, json) VALUES (?, ?, ?, ?, ?, ?)",
                ((item_id, item["state"], item["kind"], item["request"].get("priority"),
                  item["request"].get("requester"),
                  json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
                 for item_id, item in all_items.items()),
            )
    return len(all_items)


def rebuild(store):
    with store.lock():
        return _replace_locked(store)


def load_items(store):
    seq, digest = _log_head(store)
    path = _database(store)
    indexed_head = None
    try:
        with closing(sqlite3.connect(path)) as db:
            indexed_head = dict(db.execute("SELECT k, v FROM meta WHERE k IN ('last_seq', 'last_sha256')"))
            if set(indexed_head) == {"last_seq", "last_sha256"}:
                indexed_head["last_seq"] = int(indexed_head["last_seq"])
    except (sqlite3.DatabaseError, ValueError):
        indexed_head = None
    if indexed_head != {"last_seq": seq, "last_sha256": digest}:
        with store.lock():
            _replace_locked(store)
    with closing(sqlite3.connect(path)) as db:
        return {item_id: json.loads(value) for item_id, value in
                db.execute("SELECT id, json FROM items ORDER BY id")}


def _rebuild(args):
    from decide_store import Store
    store = Store(home_dir(args))
    count = rebuild(store)
    with closing(sqlite3.connect(store.home / "decide.db")) as db:
        seq = int(db.execute("SELECT v FROM meta WHERE k='last_seq'").fetchone()[0])
    emit(args, {"items": count, "last_seq": seq}, "indexed {} items at event {}".format(count, seq))
    return 0


def register(subparsers):
    command = subparsers.add_parser("rebuild")
    command.set_defaults(func=_rebuild)

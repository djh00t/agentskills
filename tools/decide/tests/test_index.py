"""Tests for the derived SQLite index."""

import hashlib
import json
import random
import sqlite3
import stat
import unittest
from contextlib import closing
from unittest.mock import patch

import decide_index
from decide_state import fold, items
from decide_store import Store
from tests.helpers import run, temp_home


BOT_IDS = ["11111111-1111-4111-8111-111111111111",
           "22222222-2222-4222-8222-222222222222",
           "33333333-3333-4333-8333-333333333333"]


def request(key="sample", kind="simple", requester=BOT_IDS[0], priority="P1"):
    return {"kind": kind, "key": key, "requester": requester,
            "title": "Sample", "priority": priority}


def append(store, event_type, item_id, data):
    with store.lock():
        return store.append(event_type, item_id, data)


class IndexTests(unittest.TestCase):
    def test_rebuild_creates_the_index_with_mode_0600(self):
        """rebuild creates the index with mode 0600"""
        home = temp_home()
        store = Store(home)
        self.assertEqual(0, decide_index.rebuild(store))
        with closing(sqlite3.connect(home / "decide.db")) as db:
            self.assertEqual(("0",), db.execute("SELECT v FROM meta WHERE k='last_seq'").fetchone())
            self.assertEqual(("0" * 64,), db.execute("SELECT v FROM meta WHERE k='last_sha256'").fetchone())
        with patch.object(decide_index, "_replace_locked", side_effect=AssertionError("unexpected rebuild")):
            self.assertEqual({}, decide_index.load_items(store))
        append(store, "ask", 1, {"request": request()})
        self.assertEqual(1, decide_index.rebuild(store))
        self.assertEqual(0o600, stat.S_IMODE((home / "decide.db").stat().st_mode))
        with closing(sqlite3.connect(home / "decide.db")) as db:
            self.assertEqual(("1",), db.execute("SELECT v FROM meta WHERE k='last_seq'").fetchone())

    def test_a_stale_index_is_rebuilt_on_read(self):
        """a stale index is rebuilt on read"""
        store = Store(temp_home())
        append(store, "ask", 1, {"request": request()})
        decide_index.rebuild(store)
        append(store, "ask", 2, {"request": request(key="next")})
        self.assertEqual({1, 2}, set(items(store)))

    def test_an_index_with_the_right_seq_but_a_different_last_hash_is_rebuilt(self):
        """an index with the right seq but a different last hash is rebuilt"""
        store = Store(temp_home())
        append(store, "ask", 1, {"request": request()})
        decide_index.rebuild(store)
        with closing(sqlite3.connect(store.home / "decide.db")) as db:
            with db:
                db.execute("UPDATE meta SET v=? WHERE k='last_sha256'", ("0" * 64,))
        self.assertEqual({1}, set(decide_index.load_items(store)))
        with closing(sqlite3.connect(store.home / "decide.db")) as db:
            expected = hashlib.sha256(store._read(store.path).splitlines()[-1]).hexdigest()
            self.assertEqual(expected, db.execute("SELECT v FROM meta WHERE k='last_sha256'").fetchone()[0])

    def test_an_index_missing_head_metadata_is_rebuilt(self):
        """an index missing head metadata is rebuilt"""
        store = Store(temp_home())
        append(store, "ask", 1, {"request": request()})
        decide_index.rebuild(store)
        with closing(sqlite3.connect(store.home / "decide.db")) as db:
            with db:
                db.execute("DELETE FROM meta WHERE k='last_seq'")
        self.assertEqual({1}, set(decide_index.load_items(store)))
        with closing(sqlite3.connect(store.home / "decide.db")) as db:
            self.assertEqual(("1",), db.execute("SELECT v FROM meta WHERE k='last_seq'").fetchone())

    def test_the_index_matches_a_fresh_fold(self):
        """the index matches a fresh fold"""
        store = Store(temp_home())
        rng = random.Random(7)
        for item_id in range(1, 31):
            request_data = request("key-{}".format(item_id),
                                   rng.choice(("simple", "complex", "pr_merge")),
                                   rng.choice(BOT_IDS), rng.choice(("P0", "P1", "P2")))
            append(store, "ask", item_id, {"request": request_data})
        expected = fold(store.read_events())
        decide_index.rebuild(store)
        with patch.object(decide_index, "_replace_locked", side_effect=AssertionError("unexpected rebuild")):
            self.assertEqual(expected, decide_index.load_items(store))
        with closing(sqlite3.connect(store.home / "decide.db")) as db:
            stored = dict(db.execute("SELECT id, json FROM items"))
        self.assertEqual({item_id: json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                          for item_id, item in expected.items()}, stored)

    def test_a_deleted_index_is_recreated(self):
        """a deleted index is recreated"""
        store = Store(temp_home())
        append(store, "ask", 1, {"request": request()})
        decide_index.rebuild(store)
        (store.home / "decide.db").unlink()
        self.assertEqual({1}, set(decide_index.load_items(store)))
        self.assertTrue((store.home / "decide.db").exists())

    def test_rebuild_command_reports_index_summary(self):
        """rebuild command reports index summary"""
        home = temp_home()
        append(Store(home), "ask", 1, {"request": request()})
        code, output, error = run(["--home", str(home), "--json", "rebuild"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"items": 1, "last_seq": 1}, json.loads(output))


if __name__ == "__main__":
    unittest.main()

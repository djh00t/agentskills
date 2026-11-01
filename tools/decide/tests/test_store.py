"""Tests for the decide event store."""

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import stat
import unittest

from decide_common import DecideError
from decide_store import Store, ZERO_HASH
from tests.helpers import run, temp_home


def _append_worker(home, worker):
    store = Store(Path(home))
    for index in range(10):
        with store.lock():
            store.append("ask", worker * 10 + index, {"worker": worker, "index": index})


class StoreTests(unittest.TestCase):
    def test_a_group_readable_home_dir_is_refused(self):
        """a group-readable home dir is refused"""
        home = temp_home()
        os.chmod(home, 0o750)
        with self.assertRaises(DecideError) as caught:
            Store(home)
        self.assertEqual(5, caught.exception.code)

    def test_the_first_event_points_at_64_zeros(self):
        """the first event points at 64 zeros"""
        store = Store(temp_home())
        with store.lock():
            event = store.append("ask", 1, {})
        self.assertEqual("0" * 64, event["prev_sha256"])

    def test_each_event_hashes_the_previous_line(self):
        """each event hashes the previous line"""
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {"text": "first"})
            store.append("ask", 2, {"text": "second"})
        lines = store.path.read_bytes().splitlines()
        self.assertEqual(hashlib.sha256(lines[0]).hexdigest(), json.loads(lines[1])["prev_sha256"])

    def test_append_outside_the_lock_is_refused(self):
        """append outside the lock is refused"""
        with self.assertRaises(RuntimeError):
            Store(temp_home()).append("ask", 1, {})

    def test_verify_log_passes_on_an_untouched_log(self):
        """verify-log passes on an untouched log"""
        home = temp_home()
        store = Store(home)
        with store.lock():
            store.append("ask", 1, {})
        result = store.verify()
        self.assertTrue(result["ok"])
        code, stdout, _ = run(["--json", "--home", str(home), "verify-log"])
        self.assertEqual(0, code)
        self.assertTrue(json.loads(stdout)["ok"])

    def test_verify_log_finds_an_edited_line(self):
        """verify-log finds an edited line"""
        store = _three_event_store()
        lines = store.path.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[1])
        event["data"]["text"] = "xwo"
        lines[1] = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _assert_broken(self, store, 3, "prev_sha256 mismatch")

    def test_verify_log_finds_a_deleted_line(self):
        """verify-log finds a deleted line"""
        store = _three_event_store()
        lines = store.path.read_bytes().splitlines()
        store.path.write_bytes(lines[0] + b"\n" + lines[2] + b"\n")
        _assert_broken(self, store, 3, "prev_sha256 mismatch")

    def test_verify_log_finds_a_non_canonical_line(self):
        """verify-log finds a non-canonical line"""
        store = _three_event_store()
        lines = store.path.read_bytes().splitlines()
        event = json.loads(lines[0])
        lines[0] = json.dumps(event, sort_keys=True, separators=(", ", ": "), ensure_ascii=False).encode("utf-8")
        store.path.write_bytes(b"\n".join(lines) + b"\n")
        _assert_broken(self, store, 1, "not canonical")

    def test_events_jsonl_is_created_with_mode_0600(self):
        """events.jsonl is created with mode 0600"""
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {})
        self.assertEqual(0o600, stat.S_IMODE(store.path.stat().st_mode))

    def test_two_processes_appending_at_once_never_break_the_chain(self):
        """two processes appending at once never break the chain"""
        home = temp_home()
        context = multiprocessing.get_context("spawn")
        workers = [context.Process(target=_append_worker, args=(str(home), worker)) for worker in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
            self.assertEqual(0, worker.exitcode)
        events = Store(home).read_events()
        self.assertTrue(Store(home).verify()["ok"])
        self.assertEqual(list(range(1, 81)), [event["seq"] for event in events])


def _three_event_store():
    store = Store(temp_home())
    with store.lock():
        for number, text in enumerate(("one", "two", "three"), 1):
            store.append("ask", number, {"text": text})
    return store


def _assert_broken(test, store, seq, reason):
    result = store.verify()
    test.assertFalse(result["ok"])
    test.assertEqual(seq, result["bad_seq"])
    test.assertEqual(reason, result["reason"])
    code, stdout, _ = run(["--json", "--home", str(store.home), "verify-log"])
    test.assertEqual(3, code)
    test.assertEqual(result, json.loads(stdout))

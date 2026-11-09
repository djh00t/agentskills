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
        events = [json.loads(line) for line in (home / "events.jsonl").read_bytes().splitlines()]
        self.assertTrue(Store(home).verify()["ok"])
        self.assertEqual(list(range(1, 81)), [event["seq"] for event in events])

    def test_verify_rejects_tampering(self):
        """verify-log rejects tampering"""
        for kind in ("reorder", "truncate", "fork", "garbled", "blank", "seq"):
            with self.subTest(kind=kind):
                store = _three_event_store()
                lines = store.path.read_bytes().splitlines()
                if kind == "reorder":
                    lines[0], lines[1] = lines[1], lines[0]
                elif kind == "truncate":
                    lines.pop()
                elif kind == "fork":
                    lines.append(lines[-1])
                elif kind == "garbled":
                    lines[-1] = b"{"
                elif kind == "blank":
                    lines.insert(1, b"")
                else:
                    event = json.loads(lines[-1])
                    event["seq"] = 7
                    lines[-1] = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
                store.path.write_bytes(b"\n".join(lines) + b"\n")
                result = store.verify()
                self.assertFalse(result["ok"])
                if kind == "seq":
                    self.assertEqual("seq gap", result["reason"])
                if kind in ("garbled", "blank"):
                    self.assertEqual("not JSON", result["reason"])
                code, out, _ = run(["--json", "--home", str(store.home), "verify-log"])
                self.assertEqual(3, code)
                self.assertEqual(result, json.loads(out))

    def test_verify_rejects_invalid_event_shape(self):
        """verify-log rejects invalid event shape"""
        for field, value in (("seq", True), ("ts", "junk"), ("type", ""), ("type", 5), ("extra", 1), ("id", None)):
            with self.subTest(field=field):
                store = _three_event_store()
                lines = store.path.read_bytes().splitlines()
                event = json.loads(lines[-1])
                if field == "id":
                    del event[field]
                else:
                    event[field] = value
                lines[-1] = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
                store.path.write_bytes(b"\n".join(lines) + b"\n")
                self.assertEqual("invalid event shape", store.verify()["reason"])

    def test_insecure_store_paths_are_refused(self):
        """insecure store paths are refused"""
        for name in ("events.jsonl", ".lock", "head"):
            for mode in (0o644, 0o666, 0o604):
                with self.subTest(name=name, mode=mode):
                    home = temp_home()
                    path = home / name
                    path.touch(mode=mode)
                    path.chmod(mode)
                    with self.assertRaises(DecideError):
                        with Store(home).lock() as store:
                            store.append("ask", 1, {})
            with self.subTest(name=name, symlink=True):
                home = temp_home()
                target = home / "target"
                target.touch(mode=0o600)
                (home / name).symlink_to(target)
                with self.assertRaises(DecideError):
                    with Store(home).lock() as store:
                        store.append("ask", 1, {})
        home = temp_home()
        (home / "events.jsonl").mkdir(mode=0o700)
        with self.assertRaises(DecideError):
            Store(home).verify()
        home = temp_home()
        home.chmod(0o705)
        with self.assertRaises(DecideError):
            Store(home)

    def test_head_recovery_after_interrupted_append(self):
        """head recovery after interrupted append"""
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {})
            old_head = store.head_path.read_bytes()
            store.append("ask", 2, {})
            store.head_path.write_bytes(old_head)
            store.append("ask", 3, {})
        self.assertTrue(store.verify()["ok"])
        self.assertEqual(3, store.verify()["events"])

    def test_head_recovery_refuses_more_than_one_event(self):
        """head recovery refuses more than one event"""
        store = _three_event_store()
        store.head_path.write_bytes(json.dumps({"seq": 1, "sha256": hashlib.sha256(store.path.read_bytes().splitlines()[0]).hexdigest()}, sort_keys=True, separators=(",", ":")).encode())
        with store.lock(), self.assertRaises(DecideError) as caught:
            store.append("ask", 4, {})
        self.assertEqual(3, caught.exception.code)

    def test_head_is_atomically_replaced_and_directory_synced(self):
        """head is atomically replaced and directory synced"""
        from unittest.mock import patch
        store = Store(temp_home())
        real_replace = os.replace
        real_fsync = os.fsync
        calls = []
        def replace(source, target):
            calls.append("replace")
            self.assertEqual(store.head_path, target)
            self.assertTrue(Path(source).is_file())
            real_replace(source, target)
        def fsync(fd):
            calls.append("directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
            real_fsync(fd)
        with patch("decide_store.os.replace", side_effect=replace), patch("decide_store.os.fsync", side_effect=fsync):
            with store.lock():
                store.append("ask", 1, {})
        self.assertEqual(["file", "directory", "file", "replace", "directory"], calls)

    def test_interrupted_head_replace_and_torn_line_recovery(self):
        """interrupted head replace and torn line recovery"""
        from unittest.mock import patch
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {})
            old_head = store.head_path.read_bytes()
            with patch("decide_store.os.replace", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    store.append("ask", 2, {})
            self.assertEqual(old_head, store.head_path.read_bytes())
            store.append("ask", 3, {})
        with store.path.open("ab") as stream:
            stream.write(b'{"seq":')
        self.assertEqual("not JSON", store.verify()["reason"])
        with store.lock():
            content = store.path.read_bytes()
            store.path.write_bytes(content[:content.rfind(b"\n") + 1])
        self.assertTrue(store.verify()["ok"])

    def test_deep_json_returns_broken_exit_3(self):
        """deep json returns broken exit 3"""
        store = Store(temp_home())
        store.path.write_bytes(b"[" * 200000 + b"\n")
        store.path.chmod(0o600)
        _assert_broken(self, store, 1, "not JSON")

    def test_missing_or_changed_head_and_broken_append(self):
        """missing or changed head and broken append"""
        for kind in ("missing", "seq"):
            with self.subTest(kind=kind):
                store = _three_event_store()
                if kind == "missing":
                    store.head_path.unlink()
                else:
                    head = json.loads(store.head_path.read_bytes())
                    head["seq"] += 1
                    store.head_path.write_text(json.dumps(head, sort_keys=True, separators=(",", ":")))
                self.assertEqual("head mismatch", store.verify()["reason"])
                with store.lock(), self.assertRaises(DecideError) as caught:
                    store.append("ask", 4, {})
                self.assertEqual(3, caught.exception.code)

    def test_lock_is_not_reentrant(self):
        """lock is not reentrant"""
        store = Store(temp_home())
        for shared in (False, True):
            with store.lock(shared=shared), self.assertRaises(RuntimeError):
                with store.lock():
                    pass

    def test_non_ascii_data_round_trips(self):
        """non ascii data round trips"""
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {"text": "café 雪"})
        self.assertEqual("café 雪", json.loads(store.path.read_bytes())["data"]["text"])
        self.assertTrue(store.verify()["ok"])

    def test_oversized_event_is_refused(self):
        """oversized event is refused"""
        store = Store(temp_home())
        with store.lock(), self.assertRaises(DecideError):
            store.append("ask", 1, {"text": "x" * 1048576})
        self.assertTrue(store.verify()["ok"])
        store.path.write_bytes(b"x" * 1048577 + b"\n")
        store.path.chmod(0o600)
        self.assertEqual("line exceeds size limit", store.verify()["reason"])

    def test_shared_lock_does_not_allow_append(self):
        """shared lock does not allow append"""
        store = Store(temp_home())
        with store.lock(shared=True), self.assertRaises(RuntimeError):
            store.append("ask", 1, {})

    def test_fifo_is_refused(self):
        """fifo is refused"""
        store = Store(temp_home())
        os.mkfifo(store.path, 0o600)
        with self.assertRaises(DecideError):
            store.verify()

    def test_home_must_be_directory(self):
        """home must be a directory"""
        home = temp_home() / "file"
        home.touch(mode=0o600)
        with self.assertRaises(DecideError):
            Store(home)

    def test_verify_rejects_missing_final_newline(self):
        """verify-log rejects a missing final newline"""
        store = _three_event_store()
        store.path.write_bytes(store.path.read_bytes().rstrip(b"\n"))
        self.assertEqual("incomplete line", store.verify()["reason"])

    def test_store_rejects_wrong_owner(self):
        """store paths with the wrong owner are refused"""
        from unittest.mock import patch
        home = temp_home()
        with patch("decide_store.os.getuid", return_value=os.getuid() + 1):
            with self.assertRaises(DecideError):
                Store(home)
        store = Store(home)
        with patch("decide_store.os.getuid", return_value=os.getuid() + 1):
            with self.assertRaises(DecideError):
                with store.lock():
                    pass

    def test_verify_waits_for_append_lock(self):
        """verify-log waits for the append lock"""
        import threading
        store = Store(temp_home())
        started = threading.Event()
        done = threading.Event()
        def verify():
            started.set()
            Store(store.home).verify()
            done.set()
        with store.lock():
            thread = threading.Thread(target=verify)
            thread.start()
            started.wait()
            self.assertFalse(done.wait(0.05))
        thread.join(2)
        self.assertTrue(done.is_set())

    def test_exact_size_limit_is_accepted(self):
        store = Store(temp_home())
        with store.lock():
            event = store.append("ask", 1, {"text": ""})
            size = len(store.path.read_bytes().rstrip(b"\n"))
            store.append("ask", 2, {"text": "x" * (1048576 - size)})
        self.assertEqual(1048576, len(store.path.read_bytes().splitlines()[1]))
        self.assertTrue(store.verify()["ok"])

    def test_other_execute_permission_is_refused(self):
        home = temp_home()
        home.chmod(0o701)
        with self.assertRaises(DecideError):
            Store(home)
        home.chmod(0o700)
        (home / ".lock").touch(mode=0o601)
        (home / ".lock").chmod(0o601)
        with self.assertRaises(DecideError):
            with Store(home).lock():
                pass

    def test_single_event_head_recovery_for_read_and_append(self):
        from unittest.mock import patch
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {})
            empty_head = json.dumps({"seq": 0, "sha256": ZERO_HASH}, sort_keys=True, separators=(",", ":")).encode()
            store.head_path.write_bytes(empty_head)
            self.assertEqual(1, len(store.read_events()))
            with patch.object(store, "_write_head", wraps=store._write_head) as write_head:
                store.append("ask", 2, {})
            self.assertEqual((1, hashlib.sha256(store.path.read_bytes().splitlines()[0]).hexdigest()), write_head.call_args_list[0].args)
        self.assertTrue(store.verify()["ok"])

    def test_broken_empty_log_with_head_is_not_recovered(self):
        store = Store(temp_home())
        store.head_path.write_bytes(b"bad")
        store.head_path.chmod(0o600)
        with self.assertRaises(DecideError):
            store.read_events()
        with store.lock(), self.assertRaises(DecideError):
            store.append("ask", 1, {})

    def test_existing_file_append_does_not_sync_creation(self):
        from unittest.mock import patch
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {})
            with patch("decide_store._sync_dir") as sync:
                store.append("ask", 2, {})
        self.assertEqual(1, sync.call_count)

    def test_reads_acquire_shared_locks(self):
        from unittest.mock import patch
        import fcntl
        store = Store(temp_home())
        with patch("decide_store.fcntl.flock", wraps=fcntl.flock) as flock:
            store.verify()
            store.read_events()
        self.assertEqual([fcntl.LOCK_SH, fcntl.LOCK_UN] * 2, [call.args[1] for call in flock.call_args_list])

    def test_lock_release_revokes_append_authority(self):
        store = Store(temp_home())
        with store.lock():
            pass
        with self.assertRaises(RuntimeError):
            store.append("ask", 1, {})

    def test_verification_rejects_ascii_escaped_unicode(self):
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {"text": "雪"})
        event = json.loads(store.path.read_bytes())
        store.path.write_text(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        self.assertEqual("not canonical", store.verify()["reason"])

    def test_recovery_does_not_accept_invalid_event_with_prior_head(self):
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {})
            prior_head = store.head_path.read_bytes()
            store.append("ask", 2, {})
            lines = store.path.read_bytes().splitlines()
            lines[-1] = b"{}"
            store.path.write_bytes(b"\n".join(lines) + b"\n")
            store.head_path.write_bytes(prior_head)
            with self.assertRaises(DecideError):
                store.read_events()
            with self.assertRaises(DecideError):
                store.append("ask", 3, {})

    def test_recovery_writes_hash_of_last_event(self):
        from unittest.mock import patch
        store = _three_event_store()
        lines = store.path.read_bytes().splitlines()
        prior_head = {"seq": 2, "sha256": hashlib.sha256(lines[1]).hexdigest()}
        store.head_path.write_text(json.dumps(prior_head, sort_keys=True, separators=(",", ":")))
        with store.lock(), patch.object(store, "_write_head", wraps=store._write_head) as write_head:
            store.append("ask", 4, {})
        self.assertEqual((3, hashlib.sha256(lines[2]).hexdigest()), write_head.call_args_list[0].args)

    def test_verification_rejects_unsorted_event_keys(self):
        store = Store(temp_home())
        with store.lock():
            store.append("ask", 1, {})
        event = json.loads(store.path.read_bytes())
        raw = json.dumps(dict(reversed(list(event.items()))), separators=(",", ":"), ensure_ascii=False).encode()
        store.path.write_bytes(raw + b"\n")
        store.head_path.write_text(json.dumps({"seq": 1, "sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True, separators=(",", ":")))
        self.assertEqual("not canonical", store.verify()["reason"])

    def test_opened_store_file_is_blocking(self):
        from decide_store import _secure_open
        home = temp_home()
        fd = _secure_open(home / "file", os.O_CREAT | os.O_RDWR)
        try:
            self.assertTrue(os.get_blocking(fd))
        finally:
            os.close(fd)


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

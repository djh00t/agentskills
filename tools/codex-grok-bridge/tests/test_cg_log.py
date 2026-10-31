import csv
import multiprocessing
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cg_log


def record_many(path, sequences):
    log = cg_log.MessageLog(path)
    for seq in sequences:
        log.record(seq, f"req-{seq}", "now")


class MessageLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "messages.tsv"
        self.log = cg_log.MessageLog(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_concurrent_processes_write_each_sequence_once(self):
        processes = [multiprocessing.Process(target=record_many, args=(self.path, range(start, 101, 2)))
                     for start in (1, 2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            self.assertEqual(process.exitcode, 0)
        rows = self.log._read()
        self.assertEqual([int(row["seq"]) for row in rows], list(range(1, 101)))

    def test_replace_failure_keeps_previous_file(self):
        self.log.record(1, "a", "now")
        original = self.path.read_bytes()
        with patch.object(cg_log.os, "replace", side_effect=OSError("simulated crash")):
            with self.assertRaises(OSError):
                self.log.record(2, "b", "later")
        self.assertEqual(self.path.read_bytes(), original)

    def test_migrate_legacy_cursor(self):
        legacy = Path(self.tmp.name) / "last-seq"
        legacy.write_text("097\n")
        log = cg_log.MessageLog(self.path, legacy)
        with patch.object(log, "_write", wraps=log._write) as write:
            self.assertEqual(log.cursor(), 97)
            self.assertEqual(write.call_count, 1)
            self.assertEqual(write.call_args.args[0][0]["seq"], "97")
        self.assertEqual(log._read()[0]["seq"], "97")
        legacy.unlink()
        self.assertEqual(cg_log.MessageLog(self.path).cursor(), 97)
        log.record(97, "duplicate", "now")
        self.assertEqual(len(log._read()), 1)

    def test_state_moves_forward_and_cursor_tracks_routed_or_later(self):
        self.log.record(3, "r", "t")
        self.assertEqual(self.log.cursor(), 2)
        self.log.transition(3, "routed")
        self.assertEqual(self.log.cursor(), 3)
        with self.assertRaises(cg_log.LogError):
            self.log.transition(3, "received")
        self.log.transition(3, "acked")
        self.log.transition(3, "done")
        with self.assertRaises(cg_log.LogError):
            self.log.transition(3, "failed")

    def test_repeat_record_is_noop(self):
        self.log.record(9, "first", "one")
        original = self.path.read_bytes()
        self.log.record(9, "other", "two")
        self.assertEqual(self.path.read_bytes(), original)


    def test_escaping_round_trip_and_metadata(self):
        value = 'tab\tquote"newline\nreturn\r\nbackslash\\snowman\u2603'
        self.log.record(1, value, value, routed_to=value, acked=value,
                        ack_msg_id=value, note=value)
        row = self.log._read()[0]
        self.assertEqual(set(row), set(cg_log.FIELDS))
        self.assertEqual(row["received_at"], value)
        for field in ("req_id", "routed_to", "acked", "ack_msg_id", "note"):
            self.assertEqual(row[field], value)
        self.log.transition(1, "routed", ack_msg_id=value + "ack", note=value + "note")
        row = self.log._read()[0]
        self.assertEqual(row["ack_msg_id"], value + "ack")
        self.assertEqual(row["note"], value + "note")

    def test_initial_state_must_be_received(self):
        for state in ("routed", "acked", "done", "failed", "unknown", None, [], {}):
            with self.subTest(state=state), self.assertRaises(cg_log.LogError):
                self.log.record(1, "r", "t", state=state)
        self.assertFalse(self.path.exists())

    def test_record_rejects_bad_sequences_and_fields(self):
        for seq in (True, False, -1, "1", 1.0, None, []):
            with self.subTest(seq=seq), self.assertRaises(cg_log.LogError):
                self.log.record(seq, "r", "t")
        for field in ("req_id", "received_at", "routed_to", "acked", "ack_msg_id", "note"):
            args = dict(req_id="r", received_at="t")
            args[field] = 1
            with self.subTest(field=field), self.assertRaises(cg_log.LogError):
                self.log.record(1, **args)

    def test_transition_rejects_bad_types(self):
        self.log.record(1, "r", "t")
        original = self.path.read_bytes()
        for seq in (True, False, -1, "1", 1.0, None, []):
            with self.subTest(seq=seq), self.assertRaises(cg_log.LogError):
                self.log.transition(seq, "routed")
        for state in (None, [], {}, 1, "unknown"):
            with self.subTest(state=state), self.assertRaises(cg_log.LogError):
                self.log.transition(1, state)
        for field in ("ack_msg_id", "note"):
            for value in (1, [], b"text"):
                with self.subTest(field=field, value=value), self.assertRaises(cg_log.LogError):
                    self.log.transition(1, "routed", **{field: value})
        self.assertEqual(self.path.read_bytes(), original)

    def test_skipped_and_unknown_transitions_fail(self):
        self.log.record(1, "r", "t")
        with self.assertRaises(cg_log.LogError):
            self.log.transition(1, "acked")
        with self.assertRaises(cg_log.LogError):
            self.log.transition(2, "routed")
        self.log.transition(1, "failed")
        self.assertEqual(self.log.cursor(), 0)
        with self.assertRaises(cg_log.LogError):
            self.log.transition(1, "done")

    def test_cursor_stops_at_unrouted_sequence(self):
        for seq in (3, 4, 5):
            self.log.record(seq, "r", "t")
        self.log.transition(3, "routed")
        self.log.transition(5, "routed")
        self.assertEqual(self.log.cursor(), 3)
        self.log.transition(4, "routed")
        self.assertEqual(self.log.cursor(), 5)

    def test_cursor_starts_before_first_received_sequence(self):
        self.log.record(4, "r", "t")
        self.log.record(5, "r", "t")
        self.log.transition(5, "routed")
        self.assertEqual(self.log.cursor(), 3)

    def test_cursor_empty_and_zero_sequence(self):
        self.assertEqual(self.log.cursor(), 0)
        self.assertFalse(self.path.exists())
        self.log.record(0, "r", "t")
        self.log.transition(0, "routed")
        self.assertEqual(self.log.cursor(), 0)

    def test_cursor_stops_at_missing_sequence(self):
        for seq in (3, 5):
            self.log.record(seq, "r", "t")
            self.log.transition(seq, "routed")
        self.assertEqual(self.log.cursor(), 3)

    def test_cursor_does_not_rewrite_existing_log(self):
        self.log.record(1, "r", "t")
        with patch.object(self.log, "_write", side_effect=AssertionError("unexpected write")):
            self.assertEqual(self.log.cursor(), 0)

    def test_invalid_legacy_values(self):
        legacy = Path(self.tmp.name) / "last-seq"
        for value in ("", "-1", "1.0", "abc", "١", "+1"):
            legacy.write_text(value)
            with self.subTest(value=value), self.assertRaises(cg_log.LogError):
                cg_log.MessageLog(self.path, legacy).cursor()
            self.assertFalse(self.path.exists())

    def test_legacy_cannot_lower_existing_cursor(self):
        self.log.record(3, "r", "t")
        self.log.transition(3, "routed")
        original = self.path.read_bytes()
        legacy = Path(self.tmp.name) / "last-seq"
        legacy.write_text("2")
        with self.assertRaises(cg_log.LogError):
            cg_log.MessageLog(self.path, legacy).cursor()
        self.assertEqual(self.path.read_bytes(), original)

    def test_record_of_legacy_sequence_persists_migration(self):
        legacy = Path(self.tmp.name) / "last-seq"
        legacy.write_text("097")
        log = cg_log.MessageLog(self.path, legacy)
        log.record(97, "duplicate", "now")
        legacy.unlink()
        self.assertEqual(self.log.cursor(), 97)

    def test_all_allowed_state_edges(self):
        for source, targets in {"received": ("routed", "failed"),
                                "routed": ("acked", "failed"),
                                "acked": ("done", "failed")}.items():
            for target in targets:
                with self.subTest(source=source, target=target):
                    path = Path(self.tmp.name) / (source + "-" + target + ".tsv")
                    log = cg_log.MessageLog(path)
                    log.record(1, "r", "t", ack_msg_id="original", note="original")
                    for state in ("routed", "acked", "done"):
                        if log._read()[0]["state"] == source:
                            break
                        log.transition(1, state)
                    log.transition(1, target)
                    row = log._read()[0]
                    self.assertEqual(row["state"], target)
                    self.assertEqual((row["ack_msg_id"], row["note"]), ("original", "original"))

    def test_migrated_cursor_can_advance_with_legacy_file_present(self):
        legacy = Path(self.tmp.name) / "last-seq"
        legacy.write_text("3")
        log = cg_log.MessageLog(self.path, legacy)
        self.assertEqual(log.cursor(), 3)
        log.record(4, "r", "t")
        log.transition(4, "routed")
        self.assertEqual(log.cursor(), 4)

    def test_invalid_utf8_log(self):
        self.path.write_bytes(b"\xff")
        with self.assertRaises(cg_log.LogError):
            self.log.cursor()

    def test_header_only_log_persists_migration(self):
        self.path.write_text("\t".join(cg_log.FIELDS) + "\n")
        legacy = Path(self.tmp.name) / "last-seq"
        legacy.write_text("097")
        self.assertEqual(cg_log.MessageLog(self.path, legacy).cursor(), 97)
        legacy.unlink()
        self.assertEqual(self.log.cursor(), 97)

    def test_invalid_log_header_and_rows(self):
        header = "\t".join(cg_log.FIELDS) + "\n"
        for content in ("bad\n", "", header + "1\tr\n",
                        header + "1\tr\tt\t\t\treceived\t\t\textra\n",
                        header + '1\tr\t"unterminated'):
            self.path.write_text(content)
            with self.subTest(content=content), self.assertRaises(cg_log.LogError):
                self.log.cursor()

    def test_corrupt_sequences_duplicates_and_states(self):
        for seq, state, duplicate in (("bad", "received", False), ("-1", "received", False),
                                       ("1.0", "received", False), ("١", "received", False),
                                       ("1", "unknown", False), ("1", "received", True)):
            row = dict.fromkeys(cg_log.FIELDS, "")
            row.update(seq=seq, state=state)
            with self.path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=cg_log.FIELDS, delimiter="\t")
                writer.writeheader()
                writer.writerow(row)
                if duplicate:
                    writer.writerow(dict(row, seq="01"))
            original = self.path.read_bytes()
            for operation in (self.log.cursor, lambda: self.log.record(2, "r", "t"),
                              lambda: self.log.transition(1, "routed")):
                with self.subTest(seq=seq, state=state, duplicate=duplicate), self.assertRaises(cg_log.LogError):
                    operation()
            self.assertEqual(self.path.read_bytes(), original)

    def test_log_and_lock_mode_are_private(self):
        previous = os.umask(0)
        try:
            self.log.record(1, "r", "t")
        finally:
            os.umask(previous)
        for path in (self.path, self.log.lock_path):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.log.transition(1, "routed")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_flock_failure_closes_handle(self):
        handles = []
        def fail(lock, operation):
            handles.append(lock)
            raise OSError("lock unavailable")
        with patch.object(cg_log.fcntl, "flock", side_effect=fail):
            with self.assertRaises(OSError):
                self.log.record(1, "r", "t")
        self.assertEqual(len(handles), 1)
        self.assertTrue(handles[0].closed)


if __name__ == "__main__":
    unittest.main()

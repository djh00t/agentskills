import multiprocessing
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
        legacy.write_text("97\n")
        log = cg_log.MessageLog(self.path, legacy)
        self.assertEqual(log.cursor(), 97)
        self.assertEqual(log.cursor(), 97)

    def test_state_moves_forward_and_cursor_tracks_routed_or_later(self):
        self.log.record(3, "r", "t")
        self.assertEqual(self.log.cursor(), 0)
        self.log.transition(3, "routed")
        self.assertEqual(self.log.cursor(), 3)
        with self.assertRaises(cg_log.LogError):
            self.log.transition(3, "received")
        self.log.transition(3, "acked")
        self.log.transition(3, "done")
        with self.assertRaises(cg_log.LogError):
            self.log.transition(3, "failed")

    def test_repeat_record_is_noop(self):
        self.log.record(9, "first", "one", state="routed")
        original = self.path.read_bytes()
        self.log.record(9, "other", "two", state="failed")
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

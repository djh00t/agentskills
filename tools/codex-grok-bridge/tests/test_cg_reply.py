import json
from datetime import datetime
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cg_reply
from cg_envelope import format_envelope
from cg_log import MessageLog


class ReplyTests(unittest.TestCase):
    def setUp(self):
        self.when = datetime(2026, 11, 1, 12, 0, tzinfo=ZoneInfo("Australia/Sydney"))

    def compose(self, **kwargs):
        base = dict(kind="result", req="REQ-CG-20261101-001", role="worker", re_seq="-",
                    reply_to="inbound-1", summary="done", routed_at=self.when)
        base.update(kwargs)
        return cg_reply.compose(**base)

    def test_ack_and_injected_clock_are_deterministic(self):
        args = dict(kind="ack", req="REQ-CG-20261101-001", role="worker", re_seq="-",
                    reply_to="inbound-1", summary="routed", routed_at=self.when)
        with patch.object(cg_reply, "format_envelope", side_effect=lambda req, kind, role, seq, body: f"[CG req={req} kind={kind} to={role} re={seq}]\n{body}"):
            self.assertEqual(cg_reply.compose(**args), cg_reply.compose(**args))
            self.assertIn("kind=ack", cg_reply.compose(**args)["message"])
            self.assertIn("routed to worker at 2026-11-01 12:00:00 AEDT; state routed", cg_reply.compose(**args)["message"])

    def test_output_is_bounded_and_summary_truncated(self):
        with patch.object(cg_reply, "format_envelope", side_effect=lambda req, kind, role, seq, body: f"[CG req={req} kind={kind} to={role} re={seq}]\n{body}"):
            output = cg_reply._json_bytes(self.compose(summary="x" * 40_000))
        self.assertLessEqual(len(output), 16_384)
        self.assertIn(cg_reply.TRUNCATION_MARKER.encode(), output)

    def test_rejects_card_and_approval_claims(self):
        for text in ("approved by the owner", "card #4", "approval recorded"):
            with self.subTest(text=text), self.assertRaises(cg_reply.ReplyError):
                self.compose(summary=text)

    def test_confirmation_requires_id_and_changes_state_only_with_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "messages.tsv"
            log = MessageLog(path)
            log.record(1, "REQ-CG-20261101-001", "now", routed_to="worker", state="received")
            log.transition(1, "routed")
            original = path.read_bytes()
            with self.assertRaises(cg_reply.ReplyError):
                cg_reply.confirm(path, 1, None)
            self.assertEqual(path.read_bytes(), original)
            cg_reply.confirm(path, 1, "outbound-1")
            self.assertIn(b"\tacked\toutbound-1\t", path.read_bytes())

    def test_module_has_no_send_or_network_call(self):
        source = Path(cg_reply.__file__).read_text()
        self.assertNotRegex(source, r"(?i)\b(requests\.|urlopen\(|message_send\s*\()")


if __name__ == "__main__":
    unittest.main()

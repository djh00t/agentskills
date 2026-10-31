import ast
import json
import tempfile
import unittest
from pathlib import Path

import cg_envelope
import cg_inbox
import cg_log


class InboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "log.tsv"
        self.log = cg_log.MessageLog(self.path)
        self.roles = Path(self.tmp.name) / "roles.json"
        self.roles.write_text(json.dumps({"chief-of-staff": "fixture-agent"}))

    def message(self, seq, sender="codex", body="hello", kind="fyi", expiry=None):
        return {"seq": seq, "sender": sender, "id": f"m{seq}", "expires_at": expiry,
                "text": cg_envelope.format_envelope("REQ-CG-20261101-001", kind,
                    "chief-of-staff", "-", body, self.roles)}

    def test_pages_filter_and_order(self):
        self.log.record(1, "old", "now", state="received")
        pages = [[self.message(4), self.message(3, sender="david")],
                 [self.message(2), self.message(5)]]
        calls = []
        def reader(conversation_id, cursor, limit):
            calls.append((conversation_id, cursor, limit))
            page = pages[len(calls) - 1]
            return {"messages": page, "next_cursor": len(calls) if len(calls) < 2 else None}
        result = cg_inbox.inbox(reader, self.log, "fixture", roles={"chief-of-staff": "agent"},
                                roles_path=self.roles)
        self.assertEqual([item["seq"] for item in result], [2, 4, 5])
        self.assertEqual(result[0]["route_to_agent_id"], "agent")

    def test_expired_is_flagged_and_needs_david_detects_terms(self):
        reader = lambda *_: {"messages": [self.message(1, body="Deploy the key", expiry=1)], "next_cursor": None}
        result = cg_inbox.inbox(reader, self.log, "fixture", roles_path=self.roles, now=2)
        self.assertTrue(result[0]["expired"])
        self.assertTrue(result[0]["needs_david"])

    def test_cli_reader_failure_leaves_log_bytes_unchanged(self):
        before = self.path.read_bytes() if self.path.exists() else b""
        result = cg_inbox.main(["fixture", "--log", str(self.path)],
                               reader=lambda *_: (_ for _ in ()).throw(OSError("offline")))
        self.assertEqual(result, 1)
        self.assertEqual(self.path.read_bytes() if self.path.exists() else b"", before)

    def test_no_send_or_ack_reference(self):
        tree = ast.parse(Path(cg_inbox.__file__).read_text())
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse({"message_send", "message_ack"} & (names | attrs))


if __name__ == "__main__":
    unittest.main()

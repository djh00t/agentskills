import ast
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cg_envelope
import cg_inbox
import cg_log


def forbidden_calls(source):
    tree = ast.parse(source)
    return {node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
            and (node.func.id if isinstance(node.func, ast.Name) else node.func.attr)
            in {"message_send", "message_ack", "record", "transition", "_locked", "cursor"}}


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

    def run_messages(self, messages, **kwargs):
        return cg_inbox.inbox(lambda *_: {"messages": messages, "next_cursor": None},
                              self.log, "fixture", roles_path=self.roles, **kwargs)

    def test_pages_filter_and_order(self):
        self.log.record(5, "old", "now")
        self.log.transition(5, "routed")
        pages = [[self.message(8), self.message(7, sender="human"), self.message(5)],
                 [self.message(6), self.message(9), self.message(3)]]
        calls = []
        def reader(conversation_id, cursor, limit):
            calls.append((conversation_id, cursor, limit))
            return {"messages": pages[len(calls) - 1],
                    "next_cursor": 1 if len(calls) == 1 else None}
        result = cg_inbox.inbox(reader, self.log, "fixture", roles_path=self.roles)
        self.assertEqual(calls, [("fixture", 5, 100), ("fixture", 1, 100)])
        self.assertEqual([item["seq"] for item in result], [6, 8, 9])
        self.assertEqual(result[0]["route_to_agent_id"], "fixture-agent")

    def test_missing_log_parent_is_not_created(self):
        log = cg_log.MessageLog(self.path.parent / "missing" / "log.tsv")
        self.assertEqual(cg_inbox.inbox(lambda *_: {"messages": [], "next_cursor": None},
                                       log, "fixture"), [])
        self.assertFalse(log.path.parent.exists())

    def test_pending_resurfaces(self):
        self.log.record(1, "old", "now")
        self.assertTrue(self.run_messages([self.message(1)])[0]["pending"])

    def test_snapshot_and_legacy_are_read_only(self):
        legacy = Path(self.tmp.name) / "legacy"
        legacy.write_text("97")
        log = cg_log.MessageLog(self.path, legacy)
        before = sorted(p.name for p in self.path.parent.iterdir())
        with patch.object(log, "_locked", side_effect=AssertionError("writer lock")):
            self.assertEqual(log.snapshot(), (97, frozenset({97})))
            result = cg_inbox.inbox(lambda *_: {"messages": [self.message(50)], "next_cursor": None},
                                    log, "fixture", roles_path=self.roles)
        self.assertEqual(result, [])
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), before)

    def test_paging_duplicates_cycles_and_cap(self):
        for tokens, count in [(["a", "b", "a"], 3), ([0], 1), ([None], 1)]:
            calls = []
            def reader(*args):
                calls.append(args)
                return {"messages": [self.message(2)], "next_cursor": tokens[len(calls)-1]}
            result = cg_inbox.inbox(reader, self.log, "fixture", roles_path=self.roles)
            self.assertEqual(len(calls), count)
            self.assertEqual([entry["seq"] for entry in result], [2])
        calls = []
        def endless(*args):
            calls.append(args)
            return {"messages": [], "next_cursor": args[1]+1}
        with self.assertRaisesRegex(cg_inbox.InboxError, "too many pages"):
            cg_inbox.inbox(endless, self.log, "fixture", max_pages=2)
        self.assertEqual(len(calls), 2)

    def test_owner_flags_warnings_and_excerpt(self):
        for term in ["merging", "credentials", "keys", "deployment", "token", "release", "approve", "key", "I4", "DEPLOY"]:
            with self.subTest(term=term):
                self.assertTrue(self.run_messages([self.message(1, body=term)])[0]["needs_owner"])
        plain = self.run_messages([self.message(1, body="x"*250)])[0]
        self.assertFalse(plain["needs_owner"])
        self.assertEqual(plain["excerpt"], "x"*200)
        self.assertFalse(plain["execution_authorized"])
        self.assertTrue(self.run_messages([self.message(1, kind="decision")])[0]["needs_owner"])
        message = self.message(1, kind="decision")
        message["text"] = message["text"].replace("chief-of-staff", "unknown")
        entry = self.run_messages([message])[0]
        self.assertEqual(entry["kind"], "decision")
        self.assertTrue(entry["needs_owner"])
        self.assertEqual(entry["warnings"], ["unknown role: unknown"])

    def test_expiry_boundary_and_clock_once(self):
        result = self.run_messages([self.message(1, expiry=10), self.message(2, expiry=11),
                                    self.message(3)], now=10)
        self.assertEqual([entry["expired"] for entry in result], [True, False, False])
        with patch("cg_inbox.time.time", return_value=10) as clock:
            self.run_messages([self.message(1), self.message(2)])
        clock.assert_called_once_with()
        for expiry in ["2026-11-01T00:00:00Z", 1793491200000, float("nan"), float("inf"), True, -1]:
            with self.subTest(expiry=expiry):
                self.assertIn("error", self.run_messages([self.message(1, expiry=expiry)])[0])

    def test_bad_messages_do_not_abort(self):
        bad = [None, {"sender": "codex"}, self.message(True), self.message(2.7), self.message("3"),
               self.message(-1), dict(self.message(4), id=""),
               dict(self.message(5), text="x"*16385), dict(self.message(6), text=None)]
        result = self.run_messages(bad + [self.message(7)])
        self.assertEqual(sum("error" in entry for entry in result), len(bad))
        self.assertTrue(all(entry["needs_owner"] for entry in result if "error" in entry))
        self.assertTrue(all("expired" in entry for entry in result))
        self.assertTrue(any(entry["seq"] == 7 and "error" not in entry for entry in result))

    def test_limit_and_max_pages_must_be_positive_integers(self):
        calls = []
        def reader(*args):
            calls.append(args)
            return {"messages": [], "next_cursor": None}
        for kwargs in [{"limit": 0}, {"limit": -1}, {"limit": 1.5}, {"limit": True}, {"limit": "5"},
                       {"max_pages": 0}, {"max_pages": -2}, {"max_pages": 2.0}, {"max_pages": False}]:
            with self.subTest(**kwargs), self.assertRaisesRegex(
                    cg_inbox.InboxError, "limit and max_pages must be positive integers"):
                cg_inbox.inbox(reader, self.log, "fixture", **kwargs)
        self.assertEqual(calls, [])

    def test_conversation_id_reaches_reader(self):
        calls = []
        def reader(*args):
            calls.append(args)
            return {"messages": [], "next_cursor": "next"} if len(calls) == 1 else {"messages": [], "next_cursor": None}
        cg_inbox.inbox(reader, self.log, "conv-42", limit=3)
        self.assertEqual([call[0] for call in calls], ["conv-42", "conv-42"])
        self.assertEqual([call[2] for call in calls], [3, 3])

    def test_sender_filter_runs_before_validity_checks(self):
        others = [dict(self.message(1), sender="human", seq="bad"), dict(self.message(2), sender=None, id="")]
        result = self.run_messages(others + [self.message(3)])
        self.assertEqual([entry["seq"] for entry in result], [3])
        self.assertFalse(any("error" in entry for entry in result))

    def test_invalid_pages(self):
        for page in [None, [], {}, {"messages": {}}, {"messages": [], "next_cursor": []}]:
            with self.subTest(page=page), self.assertRaises(cg_inbox.InboxError):
                cg_inbox.inbox(lambda *_: page, self.log, "fixture")

    def test_optional_roles_and_load_once(self):
        messages = [self.message(1), self.message(2)]
        with patch("cg_envelope.load_roles", wraps=cg_envelope.load_roles) as load:
            self.run_messages(messages)
        self.assertEqual(load.call_count, 1)
        result = cg_inbox.inbox(lambda *_: {"messages": [self.message(1)], "next_cursor": None},
                                self.log, "fixture")
        self.assertIsNone(result[0]["route_to_agent_id"])
        self.assertTrue(result[0]["needs_owner"])

    def test_cli_success_and_failure_leave_directory_unchanged(self):
        before = sorted(p.name for p in self.path.parent.iterdir())
        self.path.parent.chmod(0o555)
        self.addCleanup(self.path.parent.chmod, 0o700)
        with contextlib.redirect_stdout(io.StringIO()):
            result = cg_inbox.main(["fixture", "--log", str(self.path), "--limit", "7"],
                                   reader=lambda *args: {"messages": [], "next_cursor": None})
        self.assertEqual(result, 0)
        with contextlib.redirect_stderr(io.StringIO()):
            result = cg_inbox.main(["fixture", "--log", str(self.path)],
                                   reader=lambda *_: (_ for _ in ()).throw(OSError("offline")))
        self.assertEqual(result, 1)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), before)

    def test_cli_arguments_and_legacy(self):
        for extra in [[], ["--reader", "bad"], ["--reader", ":bad"],
                      ["--reader", "x:y", "--limit", "-5"]]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                cg_inbox.main(["fixture", "--log", str(self.path)] + extra)
            self.assertEqual(error.exception.code, 2)
        legacy = Path(self.tmp.name) / "legacy"
        legacy.write_text("97")
        calls = []
        def reader(*args):
            calls.append(args)
            return {"messages": [], "next_cursor": None}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cg_inbox.main(["fixture", "--log", str(self.path), "--legacy", str(legacy),
                                          "--limit", "7"], reader=reader), 0)
        self.assertEqual(calls, [("fixture", 97, 7)])

    def test_no_mutating_calls(self):
        self.assertFalse(forbidden_calls(Path(cg_inbox.__file__).read_text()))
        self.assertEqual(forbidden_calls("client.message_send(); log.record(); message_ack()"),
                         {"message_send", "record", "message_ack"})


if __name__ == "__main__":
    unittest.main()

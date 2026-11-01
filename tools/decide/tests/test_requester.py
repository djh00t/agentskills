"""Tests for requester state changes."""

import json
import os
import unittest

from decide_store import Store
from tests.helpers import run, temp_home


def append(store, event_type, item_id, data):
    with store.lock():
        store.append(event_type, item_id, data)


def create_item(home, kind="simple", state=None):
    store = Store(home)
    request = {"kind": kind, "key": "sample", "requester": "11111111-1111-4111-8111-111111111111",
               "title": "Sample", "priority": "P1"}
    append(store, "ask", 1, {"request": request})
    initial = "open" if kind == "pr_merge" else "ready"
    if state and state != initial:
        append(store, "transition", 1, {"from": initial, "to": state})
    return store


class RequesterTests(unittest.TestCase):
    def command(self, home, *args):
        code, output, error = run(["--json", "--home", str(home), *args])
        return code, json.loads(output) if output else None, error

    def test_withdraw_closes_a_ready_item(self):
        """withdraw closes a ready item"""
        home = temp_home()
        create_item(home)
        code, result, error = self.command(home, "withdraw", "1", "--reason", "No longer needed")
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"id": 1, "state": "withdrawn"}, result)

    def test_withdraw_on_a_closed_item_exits_3(self):
        """withdraw on a closed item exits 3"""
        home = temp_home()
        create_item(home, state="withdrawn")
        code, _, error = self.command(home, "withdraw", "1", "--reason", "No longer needed")
        self.assertEqual(3, code)
        self.assertIn("#1 is already withdrawn", error)

    def test_hold_moves_a_shown_item_to_on_hold(self):
        """hold moves a shown item to on_hold"""
        home = temp_home()
        create_item(home, state="shown")
        code, result, error = self.command(home, "hold", "1", "--reason", "Needs review")
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"id": 1, "state": "on_hold"}, result)

    def test_release_sends_a_simple_item_back_to_ready(self):
        """release sends a simple item back to ready"""
        home = temp_home()
        create_item(home, state="on_hold")
        code, result, error = self.command(home, "release", "1")
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"id": 1, "state": "ready"}, result)

    def test_release_sends_a_pr_merge_item_back_to_open(self):
        """release sends a pr_merge item back to open"""
        home = temp_home()
        create_item(home, "pr_merge", "on_hold")
        code, result, error = self.command(home, "release", "1")
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"id": 1, "state": "open"}, result)

    def test_confirm_merge_closes_an_approved_item_as_merged(self):
        """confirm-merge closes an approved item as merged"""
        home = temp_home()
        create_item(home, "pr_merge", "approved")
        sha = "a" * 40
        code, result, error = self.command(home, "confirm-merge", "1", "--sha", sha)
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"id": 1, "state": "merged"}, result)
        self.assertEqual("merge sha " + sha, Store(home).read_events()[-1]["data"]["reason"])

    def test_confirm_merge_needs_a_40_hex_sha(self):
        """confirm-merge needs a 40-hex sha"""
        home = temp_home()
        create_item(home, "pr_merge", "approved")
        code, _, error = self.command(home, "confirm-merge", "1", "--sha", "bad")
        self.assertEqual(2, code)
        self.assertIn("40 lowercase hex", error)

    def test_confirm_merge_on_a_shown_item_exits_3(self):
        """confirm-merge on a shown item exits 3"""
        home = temp_home()
        create_item(home, "pr_merge", "shown")
        code, _, error = self.command(home, "confirm-merge", "1", "--sha", "a" * 40)
        self.assertEqual(3, code)
        self.assertIn("cannot move #1", error)

    def test_merge_failed_closes_an_approved_item(self):
        """merge-failed closes an approved item"""
        home = temp_home()
        create_item(home, "pr_merge", "approved")
        code, result, error = self.command(home, "merge-failed", "1", "--reason", "Merge was blocked")
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"id": 1, "state": "merge_failed"}, result)

    def test_a_token_in_a_withdraw_reason_is_rejected(self):
        """a token in a withdraw reason is rejected"""
        home = temp_home()
        create_item(home)
        token = "g" + "hp_abcdefghijklmnopqrstuv"
        code, _, error = self.command(home, "withdraw", "1", "--reason", token)
        self.assertEqual(2, code)
        self.assertIn("sensitive token", error)

    def test_requester_reasons_must_be_safe_and_at_most_200_characters(self):
        """requester reasons must be safe and at most 200 characters"""
        for reason in ("x", "x" * 200):
            with self.subTest(valid_length=len(reason)):
                home = temp_home()
                create_item(home)
                code, _, _ = self.command(home, "withdraw", "1", "--reason", reason)
                self.assertEqual(0, code)
        for reason in ("", "x" * 201, "line\nbreak"):
            with self.subTest(reason_length=len(reason)):
                home = temp_home()
                create_item(home)
                code, _, _ = self.command(home, "withdraw", "1", "--reason", reason)
                self.assertEqual(2, code)

    def test_requester_commands_reject_an_unknown_item(self):
        """requester commands reject an unknown item"""
        home = temp_home()
        create_item(home)
        code, _, error = self.command(home, "withdraw", "2", "--reason", "No longer needed")
        self.assertEqual(4, code)
        self.assertIn("no item #2", error)

    def test_requester_commands_reject_a_broken_event_log(self):
        """requester commands reject a broken event log"""
        home = temp_home()
        create_item(home)
        store = Store(home)
        store.path.write_bytes(b"{}\n")
        os.chmod(store.path, 0o600)
        code, _, error = self.command(home, "withdraw", "1", "--reason", "No longer needed")
        self.assertEqual(3, code)
        self.assertIn("cannot read a broken log", error)

    def test_reason_and_sha_options_are_required(self):
        """reason and sha options are required"""
        code, _, error = run(["--home", str(temp_home()), "withdraw", "1"])
        self.assertEqual(2, code)
        self.assertIn("required", error)
        code, _, error = run(["--home", str(temp_home()), "confirm-merge", "1"])
        self.assertEqual(2, code)
        self.assertIn("required", error)


if __name__ == "__main__":
    unittest.main()

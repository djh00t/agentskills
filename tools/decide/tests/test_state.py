"""Tests for item state and read commands."""

import json
import unittest

from decide_common import DecideError
from decide_state import check_transition, fold, get_item, write_transition
from decide_store import Store
from tests.helpers import run, temp_home


def append(store, event_type, item_id, data):
    with store.lock():
        return store.append(event_type, item_id, data)


def request(kind="simple", key="sample"):
    return {"kind": kind, "key": key, "requester": "11111111-1111-4111-8111-111111111111",
            "title": "Sample", "priority": "P1"}


def asked(store, kind="simple", key="sample", item_id=1):
    append(store, "ask", item_id, {"request": request(kind, key)})
    return fold(store.read_events())[item_id]


class StateTests(unittest.TestCase):
    def test_a_new_simple_item_starts_ready(self):
        """a new simple item starts ready"""
        item = asked(Store(temp_home()))
        self.assertEqual("ready", item["state"])
        self.assertFalse(item["legacy"])

    def test_a_new_pr_merge_item_starts_open(self):
        """a new pr_merge item starts open"""
        self.assertEqual("open", asked(Store(temp_home()), "pr_merge")["state"])

    def test_a_simple_item_cannot_be_approved(self):
        """a simple item cannot be approved"""
        with self.assertRaises(DecideError) as caught:
            check_transition(asked(Store(temp_home())), "approved")
        self.assertEqual((3, "cannot move #1 from ready to approved"),
                         (caught.exception.code, caught.exception.message))

    def test_a_pr_merge_item_cannot_go_from_open_to_approved(self):
        """a pr_merge item cannot go from open to approved"""
        with self.assertRaises(DecideError):
            check_transition(asked(Store(temp_home()), "pr_merge"), "approved")

    def test_nothing_leaves_a_closed_state(self):
        """nothing leaves a closed state"""
        item = asked(Store(temp_home()))
        item["state"] = "answered"
        with self.assertRaises(DecideError):
            check_transition(item, "ready")

    def test_an_approved_pr_merge_item_can_only_be_merged_or_fail(self):
        """an approved pr_merge item can only be merged or fail"""
        item = asked(Store(temp_home()), "pr_merge")
        item["state"] = "approved"
        check_transition(item, "merged")
        check_transition(item, "merge_failed")
        with self.assertRaises(DecideError):
            check_transition(item, "ready")

    def test_write_transition_keeps_optional_fields_only_when_present(self):
        """write_transition keeps optional fields only when present"""
        store = Store(temp_home())
        item = asked(store)
        with store.lock():
            event = write_transition(store, item, "shown", reason="prompt", by="operator")
        self.assertEqual({"from": "ready", "to": "shown", "reason": "prompt", "by": "operator"}, event["data"])
        item["state"] = "shown"
        with store.lock():
            event = write_transition(store, item, "answered")
        self.assertEqual({"from": "shown", "to": "answered"}, event["data"])

    def test_fold_applies_import_and_timestamp_fields(self):
        """fold applies import and timestamp fields"""
        events = [
            {"seq": 1, "ts": "2026-01-05T00:00:00Z", "type": "import", "id": 2,
             "data": {"record": {"id": 2, "kind": "simple", "state": "ready", "rank": 7,
                                  "created_at": "2026-01-01T00:00:00Z", "title": "Old", "requester": "11111111-1111-4111-8111-111111111111"}}},
            {"seq": 2, "ts": "2026-01-05T00:01:00Z", "type": "transition", "id": 2,
             "data": {"from": "ready", "to": "shown"}},
            {"seq": 3, "ts": "2026-01-05T00:02:00Z", "type": "chase", "id": 2, "data": {}},
            {"seq": 4, "ts": "2026-01-05T00:03:00Z", "type": "verify", "id": 2, "data": {"ok": True}},
            {"seq": 5, "ts": "2026-01-05T00:04:00Z", "type": "amend", "id": 2,
             "data": {"request": request(key="updated")}},
            {"seq": 6, "ts": "2026-01-05T00:05:00Z", "type": "transition", "id": 2,
             "data": {"from": "shown", "to": "answered"}},
        ]
        item = fold(events)[2]
        self.assertTrue(item["legacy"])
        self.assertEqual(7, item["rank"])
        self.assertEqual("2026-01-01T00:00:00Z", item["created_at"])
        self.assertEqual("2026-01-05T00:05:00Z", item["updated_at"])
        self.assertEqual("2026-01-05T00:05:00Z", item["closed_at"])
        self.assertEqual("2026-01-05T00:02:00Z", item["last_shown_at"])
        self.assertEqual({"ok": True}, item["verify"])
        self.assertEqual("updated", item["request"]["key"])
        self.assertNotIn("id", item["request"])
        self.assertNotIn("state", item["request"])
        self.assertNotIn("rank", item["request"])
        imported = fold(events[:1])[2]
        self.assertEqual({"kind": "simple", "created_at": "2026-01-01T00:00:00Z",
                          "title": "Old", "requester": "11111111-1111-4111-8111-111111111111"},
                         imported["request"])

    def test_get_item_returns_items_and_reports_missing_ids(self):
        """get_item returns items and reports missing ids"""
        store = Store(temp_home())
        asked(store)
        self.assertEqual(1, get_item(store, 1)["id"])
        with self.assertRaises(DecideError) as caught:
            get_item(store, 9)
        self.assertEqual((4, "no item #9"), (caught.exception.code, caught.exception.message))

    def test_fold_refuses_an_event_for_an_unknown_item(self):
        """fold refuses an event for an unknown item"""
        event = {"seq": 1, "ts": "2026-01-05T00:00:00Z", "type": "answer",
                 "id": 9, "data": {}, "prev_sha256": "0" * 64}
        with self.assertRaisesRegex(DecideError, "event 1 refers to unknown item 9") as caught:
            fold([event])
        self.assertEqual(5, caught.exception.code)

    def test_status_shows_the_answer_words_once_answered(self):
        """status shows the answer words once answered"""
        home = temp_home()
        store = Store(home)
        asked(store)
        append(store, "answer", 1, {"choice": "A", "label": "A", "words": "Proceed"})
        code, output, error = run(["--json", "--home", str(home), "status", "1"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"id": 1, "state": "ready", "kind": "simple", "title": "Sample",
                          "answer": {"choice": "A", "label": "A", "words": "Proceed"}}, json.loads(output))

    def test_status_by_requester_and_key_finds_the_item(self):
        """status by requester and key finds the item"""
        home = temp_home()
        asked(Store(home), key="sample-key")
        asked(Store(home), key="other-key", item_id=2)
        append(Store(home), "ask", 3, {"request": dict(request(key="sample-key"),
                                                        requester="22222222-2222-4222-8222-222222222222")})
        code, output, error = run(["--json", "--home", str(home), "status", "--requester",
                                   "11111111-1111-4111-8111-111111111111", "--key", "sample-key"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual(1, json.loads(output)["id"])
        code, output, error = run(["--json", "--home", str(home), "status", "--requester",
                                   "11111111-1111-4111-8111-111111111111", "--key", "other-key"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual(2, json.loads(output)["id"])

    def test_status_by_missing_requester_and_key_exits_4(self):
        """status by missing requester and key exits 4"""
        code, output, error = run(["--home", str(temp_home()), "status", "--requester",
                                   "11111111-1111-4111-8111-111111111111", "--key", "missing"])
        self.assertEqual(4, code)
        self.assertEqual("", output)
        self.assertIn("no item for requester and key", error)

    def test_status_requires_requester_and_key_together(self):
        """status requires requester and key together"""
        code, output, error = run(["--home", str(temp_home()), "status", "--requester",
                                   "11111111-1111-4111-8111-111111111111"])
        self.assertEqual((2, ""), (code, output))
        self.assertIn("requires both requester and key", error)

    def test_status_of_a_missing_item_exits_4(self):
        """status of a missing item exits 4"""
        code, output, error = run(["--home", str(temp_home()), "status", "8"])
        self.assertEqual(4, code)
        self.assertEqual("", output)
        self.assertIn("no item #8", error)

    def test_list_open_hides_closed_items(self):
        """list --open hides closed items"""
        home = temp_home()
        store = Store(home)
        asked(store, item_id=1)
        append(store, "transition", 1, {"from": "ready", "to": "answered"})
        asked(store, key="open-item", item_id=2)
        append(store, "ask", 3, {"request": dict(request(key="third-item"),
                                                requester="22222222-2222-4222-8222-222222222222")})
        code, output, error = run(["--json", "--home", str(home), "list", "--open"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual([{"id": 2, "state": "ready", "priority": "P1", "title": "Sample",
                           "requester": "11111111-1111-4111-8111-111111111111"},
                          {"id": 3, "state": "ready", "priority": "P1", "title": "Sample",
                           "requester": "22222222-2222-4222-8222-222222222222"}], json.loads(output))
        code, output, error = run(["--json", "--home", str(home), "list", "--requester",
                                   "22222222-2222-4222-8222-222222222222"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual(["22222222-2222-4222-8222-222222222222"],
                         [row["requester"] for row in json.loads(output)])


if __name__ == "__main__":
    unittest.main()

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
    from pathlib import Path
    filename = {"simple": "simple_ok.json", "complex": "complex_ok.json", "pr_merge": "pr_merge_ok.json"}[kind]
    obj = json.loads((Path(__file__).parent / "fixtures" / "requests" / filename).read_text())
    obj.pop("cc", None)
    obj.update(key=key, title="Sample", priority="P1")
    return obj


def asked(store, kind="simple", key="sample", item_id=1):
    append(store, "ask", item_id, {"request": request(kind, key)})
    return fold(store.read_events())[item_id]


class StateTests(unittest.TestCase):
    def test_invalid_payload_and_duplicate_are_refused(self):
        store = Store(temp_home())
        append(store, "ask", 1, {"request": {}})
        with self.assertRaises(DecideError):
            fold(store.read_events())
        store = Store(temp_home())
        asked(store)
        append(store, "ask", 1, {"request": request()})
        with self.assertRaises(DecideError):
            fold(store.read_events())

    def test_stale_transition_is_refused(self):
        """stale transitions are refused"""
        store = Store(temp_home())
        item = asked(store)
        with store.lock():
            write_transition(store, item, "shown")
        with store.lock():
            with self.assertRaises(DecideError) as caught:
                write_transition(store, item, "expired")
            self.assertEqual(3, caught.exception.code)
        self.assertEqual("shown", fold(store.read_events())[1]["state"])
        self.assertEqual(2, len(store.read_events()))

    def test_illegal_transition_write_is_refused(self):
        """illegal transition writes are refused"""
        store = Store(temp_home())
        item = asked(store)
        with store.lock(), self.assertRaises(DecideError) as caught:
            write_transition(store, item, "merged")
        self.assertEqual(3, caught.exception.code)
        self.assertEqual(1, len(store.read_events()))

    def test_legacy_states_must_be_reachable_for_the_kind(self):
        """legacy states must be reachable for the kind"""
        for kind in ("simple", "complex"):
            for state in ("open", "approved", "merged", "merge_failed"):
                store = Store(temp_home())
                append(store, "import", 1, {"record": dict(request(kind), id=1, state=state)})
                with self.subTest(kind=kind, state=state):
                    with self.assertRaises(DecideError) as caught:
                        fold(store.read_events())
                    self.assertEqual(3, caught.exception.code)
        store = Store(temp_home())
        append(store, "import", 1, {"record": dict(request(), id=1, state="answered", created_at="2026-01-01T00:00:00Z")})
        self.assertEqual("2026-01-01T00:00:00Z", fold(store.read_events())[1]["closed_at"])

    def test_valid_pr_merge_legacy_states_load_with_correct_closed_at(self):
        """valid pr_merge legacy states load and set closed_at only when closed"""
        for state in ("open", "approved", "merged"):
            with self.subTest(state=state):
                store = Store(temp_home())
                record = dict(request("pr_merge"), id=1, state=state,
                              created_at="2026-01-01T00:00:00Z")
                append(store, "import", 1, {"record": record})
                item = fold(store.read_events())[1]
                self.assertEqual(state, item["state"])
                if state == "merged":
                    self.assertEqual("2026-01-01T00:00:00Z", item["closed_at"])
                else:
                    self.assertIsNone(item["closed_at"])

    def test_non_string_transition_target_is_refused(self):
        for target in ([], {}):
            store = Store(temp_home())
            asked(store)
            append(store, "transition", 1, {"from": "ready", "to": target})
            with self.assertRaises(DecideError) as caught:
                fold(store.read_events())
            self.assertEqual(3, caught.exception.code)

    def test_status_refuses_id_with_requester_and_key(self):
        self.assertEqual(2, run(["status", "1", "--requester", "a", "--key", "b"])[0])

    def test_read_refuses_head_more_than_one_event_behind(self):
        store = Store(temp_home())
        append(store, "page_ack", None, {})
        old_head = store.head_path.read_bytes()
        append(store, "page_ack", None, {})
        append(store, "page_ack", None, {})
        store.head_path.write_bytes(old_head)
        with self.assertRaises(DecideError) as caught:
            store.read_events()
        self.assertEqual(3, caught.exception.code)

    def test_null_page_ack_allows_later_writes(self):
        """a null page acknowledgement permits later writes"""
        store = Store(temp_home())
        append(store, "page_ack", None, {})
        asked(store)
        self.assertEqual("ready", get_item(store, 1)["state"])

    def test_read_events_refuses_broken_log(self):
        """broken logs are refused by reads"""
        store = Store(temp_home())
        asked(store)
        store.path.write_bytes(b"broken\n")
        with self.assertRaises(DecideError):
            store.read_events()

    def test_invalid_events_return_conflict_codes(self):
        event = {"seq": 1, "ts": "2026-01-05T00:00:00Z", "type": "ask", "id": 1, "data": {}, "prev_sha256": "0" * 64}
        cases = [([{}], "invalid event"), ([event, event], "duplicate item"),
                 ([dict(event, type="import", data={})], "invalid legacy record"),
                 ([dict(event, type="import", data={"record": dict(request(), id=2, state="ready")})], "legacy id mismatch")]
        cases[1] = ([dict(event, data={"request": request()}), dict(event, data={"request": request()})], "duplicate item")
        for events, message in cases:
            with self.subTest(message=message), self.assertRaises(DecideError) as caught:
                fold(events)
            self.assertEqual(3, caught.exception.code)
        for event_type, data in [("transition", {"from": "shown", "to": "answered"}), ("answer", {}), ("amend", {"request": {}}), ("amend", {"request": request("pr_merge")})]:
            store = Store(temp_home())
            asked(store)
            append(store, event_type, 1, data)
            with self.assertRaises(DecideError) as caught:
                fold(store.read_events())
            self.assertEqual(3, caught.exception.code)
        store = Store(temp_home())
        append(store, "page_ack", 9, {})
        with self.assertRaises(DecideError):
            fold(store.read_events())

    def test_invalid_legacy_and_unsafe_titles_fail_cleanly(self):
        for record in ({"id": 1, "kind": "simple", "state": "ready", "title": "Old"},
                       dict(request("pr_merge"), id=1, state="approved", pr=dict(request("pr_merge")["pr"], head_sha="abcdef0"))):
            store = Store(temp_home())
            append(store, "import", 1, {"record": record})
            self.assertEqual(3, run(["--home", str(store.home), "list"])[0])
        for title in ("bad\nrow", "bad\u202erow"):
            store = Store(temp_home())
            append(store, "ask", 1, {"request": dict(request(), title=title)})
            for command in (["list"], ["status", "1"]):
                self.assertEqual(3, run(["--home", str(store.home)] + command)[0])

    def test_read_accepts_head_one_event_behind(self):
        store = Store(temp_home())
        append(store, "page_ack", None, {})
        previous_head = store.head_path.read_bytes()
        asked(store)
        store.head_path.write_bytes(previous_head)
        self.assertEqual(2, len(store.read_events()))
        append(store, "counter_floor", None, {})
        self.assertEqual(3, len(store.read_events()))

    def test_transition_matrix_and_closed_set(self):
        from decide_schema import KINDS, STATES
        from decide_state import CLOSED
        common = {"ready": "shown on_hold withdrawn superseded expired answered rejected", "shown": "answered rejected on_hold withdrawn superseded expired", "on_hold": "ready withdrawn superseded expired"}
        pr = {"open": "ready on_hold withdrawn superseded expired", "ready": "open shown on_hold withdrawn superseded expired approved answered rejected", "shown": "open approved answered rejected on_hold withdrawn superseded expired", "on_hold": "open withdrawn superseded expired", "approved": "merged merge_failed"}
        self.assertEqual(set("answered rejected merged merge_failed expired withdrawn superseded".split()), CLOSED)
        for kind in KINDS:
            for source in STATES:
                for target in STATES:
                    item = {"id": 1, "kind": kind, "state": source}
                    allowed = target in (pr if kind == "pr_merge" else common).get(source, "").split()
                    with self.subTest(kind=kind, source=source, target=target):
                        if allowed:
                            check_transition(item, target)
                        else:
                            with self.assertRaises(DecideError):
                                check_transition(item, target)

    def test_bad_transitions_and_ids_fail(self):
        for source, target in [("ready", "merged"), ("shown", "answered")]:
            store = Store(temp_home())
            asked(store)
            append(store, "transition", 1, {"from": source, "to": target})
            with self.assertRaises(DecideError):
                fold(store.read_events())
        for value in [None, "0", "-1", " 1 ", "0_1", "١"]:
            args = ["status"] + ([] if value is None else [value])
            self.assertEqual(2, run(args)[0])

    def test_other_schema_event_types_fold(self):
        store = Store(temp_home())
        asked(store)
        for kind in ("closed_by", "outbox", "outbox_sent", "page_ack", "counter_floor"):
            append(store, kind, None if kind in ("page_ack", "counter_floor") else 1, {})
        self.assertEqual("ready", get_item(store, 1)["state"])

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
             "data": {"record": dict(request(), id=2, state="ready", rank=7, created_at="2026-01-01T00:00:00Z", title="Old")}},
            {"seq": 2, "ts": "2026-01-05T00:01:00Z", "type": "transition", "id": 2,
             "data": {"from": "ready", "to": "shown"}},
            {"seq": 3, "ts": "2026-01-05T00:02:00Z", "type": "chase", "id": 2, "data": {}},
            {"seq": 4, "ts": "2026-01-05T00:03:00Z", "type": "verify", "id": 2, "data": {"ok": True}},
            {"seq": 5, "ts": "2026-01-05T00:04:00Z", "type": "amend", "id": 2,
             "data": {"request": request(key="updated")}},
            {"seq": 6, "ts": "2026-01-05T00:05:00Z", "type": "transition", "id": 2,
             "data": {"from": "shown", "to": "answered"}},
        ]
        for event in events:
            event["prev_sha256"] = "0" * 64
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
        self.assertEqual("Old", imported["request"]["title"])

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
        self.assertEqual(3, caught.exception.code)

    def test_status_shows_the_answer_words_once_answered(self):
        """status shows the answer words once answered"""
        home = temp_home()
        store = Store(home)
        asked(store)
        append(store, "answer", 1, {"choice": "A", "label": "A", "words": "Proceed", "via": "card", "msg_ref": "ref", "mapped_by": "token", "closes": [], "recorded_by": "record"})
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

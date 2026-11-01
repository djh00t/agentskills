"""Tests for the reply outbox."""

import json
import unittest

from decide_outbox import TEMPLATES, pending, queue_for_item
from decide_store import Store
from tests.helpers import run, temp_home


REQUESTER = "11111111-1111-4111-8111-111111111111"
CC = "22222222-2222-4222-8222-222222222222"
FIELDS = {"label": "A", "text": "Proceed", "words": "Go ahead"}


def item(requester=REQUESTER, cc=None, item_id=1):
    request = {"requester": requester, "cc": [] if cc is None else cc}
    return {"id": item_id, "request": request}


def queue_item(store, value, template="answered", fields=None):
    with store.lock():
        return queue_for_item(store, value, template, FIELDS if fields is None else fields)


class OutboxTests(unittest.TestCase):
    def test_an_answer_queues_one_requester_line_at_priority_true(self):
        """an answer queues one requester line at priority true"""
        home = temp_home()
        store = Store(home)
        queue_item(store, item(), fields={"label": "A", "text": "Proceed", "words": "Go ahead é"})
        self.assertEqual([{"oid": "1-1", "to": REQUESTER, "priority": True,
                           "text": 'decide #1 answered: A (Proceed). Words: "Go ahead é"'}], pending(store))
        code, output, error = run(["--home", str(home), "outbox"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual('1-1 -> {} [P]: decide #1 answered: A (Proceed). Words: "Go ahead é"\n'.format(REQUESTER), output)
        code, output, error = run(["--json", "--home", str(home), "outbox"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual({"oid": "1-1", "to": REQUESTER, "priority": True,
                          "text": 'decide #1 answered: A (Proceed). Words: "Go ahead é"'},
                         json.loads(output))
        self.assertIn('"to": "' + REQUESTER + '"', output)
        self.assertIn("é", output)

    def test_each_cc_gets_an_fyi_line_at_priority_false(self):
        """each cc gets an FYI line at priority false"""
        store = Store(temp_home())
        queue_item(store, item(cc=[CC, REQUESTER]))
        lines = pending(store)
        self.assertEqual(3, len(lines))
        self.assertEqual([REQUESTER, CC, REQUESTER], [line["to"] for line in lines])
        self.assertEqual([True, False, False], [line["priority"] for line in lines])
        self.assertTrue(all(line["text"].startswith("FYI ") for line in lines[1:]))

    def test_an_expired_item_tells_the_requester_at_priority_false(self):
        """an expired item tells the requester at priority false"""
        store = Store(temp_home())
        queue_item(store, item(), "expired", {})
        self.assertFalse(pending(store)[0]["priority"])
        self.assertEqual("decide #1 expired with no answer. It is not a yes and not a no.",
                         pending(store)[0]["text"])

    def test_a_legacy_item_with_no_requester_queues_only_cc_lines(self):
        """a legacy item with no requester queues only cc lines"""
        store = Store(temp_home())
        queue_item(store, item(requester=None, cc=[CC]))
        self.assertEqual([(CC, False)], [(line["to"], line["priority"]) for line in pending(store)])

    def test_mark_sent_removes_the_line_from_pending(self):
        """mark-sent removes the line from pending"""
        home = temp_home()
        store = Store(home)
        queue_item(store, item())
        code, _, error = run(["--home", str(home), "outbox", "--mark-sent", "1-1"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual([], pending(store))

    def test_mark_sent_twice_exits_3(self):
        """mark-sent twice exits 3"""
        home = temp_home()
        queue_item(Store(home), item())
        self.assertEqual(0, run(["--home", str(home), "outbox", "--mark-sent", "1-1"])[0])
        code, output, error = run(["--home", str(home), "outbox", "--mark-sent", "1-1"])
        self.assertEqual((3, ""), (code, output))
        self.assertIn("already sent", error)

    def test_an_unknown_oid_exits_4(self):
        """an unknown oid exits 4"""
        home = temp_home()
        store = Store(home)
        with store.lock():
            store.append("outbox_sent", 1, {"oid": "1-9"})
        code, output, error = run(["--home", str(home), "outbox", "--mark-sent", "1-9"])
        self.assertEqual((4, ""), (code, output))
        self.assertIn("no outbox line", error)

    def test_text_is_the_exact_template(self):
        """text is the exact template"""
        self.assertEqual({
            "answered": 'decide #{id} answered: {label} ({text}). Words: "{words}"',
            "custom": 'decide #{id} answered (custom). Words: "{words}"',
            "approved": ('decide #{id} approved: {label} ({text}). Words: "{words}". '
                         'Merge it, then run decide confirm-merge {id} --sha <merge sha>.'),
            "rejected": "decide #{id} rejected with no reason.",
            "expired": "decide #{id} expired with no answer. It is not a yes and not a no.",
            "verify_failed": "decide #{id} verify-pr failed: {reasons}.",
            "stale": "decide #{id} is stale: the PR head changed. Re-run verify-pr at the new head.",
            "closed_by": 'decide #{id} closed as {label} by the answer on #{by}. Words: "{words}"',
        }, TEMPLATES)


if __name__ == "__main__":
    unittest.main()

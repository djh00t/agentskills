"""Tests for the pull request verification plan command."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from decide_store import Store
from tests.helpers import run, temp_home


FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "requests"


def add_item(home, kind="pr_merge", closed=False):
    fixture = FIXTURE / ("pr_merge_ok.json" if kind == "pr_merge" else "simple_ok.json")
    request = json.loads(fixture.read_text(encoding="utf-8"))
    store = Store(home)
    with store.lock():
        store.append("ask", 1, {"request": request})
        if closed:
            store.append("transition", 1, {"from": "open", "to": "expired"})
    return store


class VerifyPlanTests(unittest.TestCase):
    def test_the_plan_has_four_calls_in_a_fixed_order(self):
        """the plan has four calls in a fixed order"""
        home = temp_home()
        add_item(home)
        code, output, error = run(["--home", str(home), "verify-pr", "1"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual([
            {"tool": "get_pull_request", "arguments": {"owner": "example-org", "repo": "example-repo",
                                                          "pull_number": 1}, "save_as": "pr.json"},
            {"tool": "list_pull_request_reviews", "arguments": {"owner": "example-org", "repo": "example-repo",
                                                                   "pull_number": 1, "per_page": 100},
             "save_as": "reviews.json", "fail_closed": "page contains 100 reviews"},
            {"tool": "list_check_runs_for_ref", "arguments": {"owner": "example-org", "repo": "example-repo",
                                                               "ref": "a" * 40, "per_page": 100},
             "save_as": "checks.json", "fail_closed": "page contains 100 check runs or total_count exceeds returned runs"},
            {"tool": "get_commit_combined_status", "arguments": {"owner": "example-org", "repo": "example-repo",
                                                                     "ref": "a" * 40}, "save_as": "status.json"},
        ], json.loads(output))

    def test_unknown_item_has_no_plan(self):
        """an unknown item has no plan"""
        home = temp_home()
        code, output, error = run(["--home", str(home), "verify-pr", "99"])
        self.assertEqual((4, "", "decide: error: no item #99\n"), (code, output, error))

    def test_invalid_stored_request_has_no_plan(self):
        """an invalid stored request has no plan"""
        original = json.loads((FIXTURE / "pr_merge_ok.json").read_text(encoding="utf-8"))
        for field, value in [("head_sha", "abc1234"), ("head_sha", "main"),
                             ("head_sha", "A" * 40), ("repo", "owner/repo\n"),
                             ("repo", "invalid"), ("number", "1; rm"),
                             ("number", True), ("number", 0), ("head_sha", None),
                             ("pr", None)]:
            with self.subTest(field=field, value=value):
                request = json.loads(json.dumps(original))
                if field == "pr":
                    del request["pr"]
                elif value is None:
                    del request["pr"][field]
                else:
                    request["pr"][field] = value
                item = {"kind": "pr_merge", "state": "open", "request": request}
                with patch("decide_verify.get_item", return_value=item):
                    code, output, error = run(["--home", str(temp_home()), "verify-pr", "1"])
                self.assertEqual(2, code)
                self.assertEqual("", output)
                self.assertEqual("decide: error: invalid stored request\n", error)

    def test_item_ids_use_ascii_decimal_digits(self):
        """item ids use ASCII decimal digits"""
        for command in ("verify-pr", "status"):
            for value in (" 1 ", "0_1", "١"):
                with self.subTest(command=command, value=value):
                    code, output, _ = run(["--home", str(temp_home()), command, value])
                    self.assertEqual((2, ""), (code, output))

    def test_a_simple_item_has_no_plan(self):
        """a simple item has no plan"""
        home = temp_home()
        add_item(home, kind="simple")
        code, output, error = run(["--home", str(home), "verify-pr", "1"])
        self.assertEqual(2, code)
        self.assertEqual("", output)
        self.assertEqual("decide: error: item must be pr_merge\n", error)

    def test_a_closed_pr_merge_item_has_no_plan(self):
        """a closed pr_merge item has no plan"""
        home = temp_home()
        add_item(home, closed=True)
        code, output, error = run(["--home", str(home), "verify-pr", "1"])
        self.assertEqual(3, code)
        self.assertEqual("", output)
        self.assertEqual("decide: error: item is closed\n", error)

    def test_verify_pr_writes_nothing(self):
        """verify-pr writes nothing"""
        home = temp_home()
        store = add_item(home)
        before = store.path.read_bytes()
        code, _, error = run(["--home", str(home), "verify-pr", "1"])
        self.assertEqual((0, ""), (code, error))
        self.assertEqual(before, store.path.read_bytes())
        self.assertEqual([".lock", "events.jsonl", "head"], sorted(p.name for p in home.iterdir()))

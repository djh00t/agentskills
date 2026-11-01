"""Request schema validation tests."""

import json
from pathlib import Path
import unittest

from decide_schema import validate_request


FIXTURES = Path(__file__).parent / "fixtures" / "requests"


def fixture(name):
    return json.loads((FIXTURES / (name + "_ok.json")).read_text(encoding="utf-8"))


class RequestSchemaTests(unittest.TestCase):
    def test_the_three_sample_requests_are_valid(self):
        """the three sample requests are valid"""
        for name in ("simple", "complex", "pr_merge"):
            with self.subTest(name=name):
                self.assertEqual([], validate_request(fixture(name)))

    def test_a_request_with_an_unknown_field_is_invalid(self):
        """a request with an unknown field is invalid"""
        obj = fixture("simple")
        obj["mystery"] = True
        self.assertEqual(["mystery: unknown field"], validate_request(obj))

    def test_a_title_longer_than_80_characters_is_invalid(self):
        """a title longer than 80 characters is invalid"""
        obj = fixture("simple")
        obj["title"] = "x" * 81
        self.assertEqual(["title: longer than 80 characters"], validate_request(obj))

    def test_a_request_needs_exactly_one_recommended_option(self):
        """a request needs exactly one recommended option"""
        obj = fixture("simple")
        obj["options"][1]["rec"] = True
        self.assertEqual(["options: must have exactly one recommended option"], validate_request(obj))

    def test_option_labels_must_run_a_b_c_in_order(self):
        """option labels must run A, B, C in order"""
        obj = fixture("simple")
        obj["options"][1]["label"] = "C"
        self.assertEqual(["options[1].label: must be B"], validate_request(obj))

    def test_approves_merge_is_only_allowed_on_pr_merge(self):
        """approves_merge is only allowed on pr_merge"""
        obj = fixture("simple")
        obj["options"][0]["approves_merge"] = True
        self.assertEqual(["options[0].approves_merge: only allowed for pr_merge"], validate_request(obj))

    def test_a_pr_merge_request_needs_exactly_one_approves_merge_option(self):
        """a pr_merge request needs exactly one approves_merge option"""
        obj = fixture("pr_merge")
        obj["options"][0]["approves_merge"] = False
        self.assertEqual(["options: must have exactly one approves_merge option"], validate_request(obj))

    def test_a_pr_merge_request_needs_a_40_hex_head_sha(self):
        """a pr_merge request needs a 40-hex head sha"""
        obj = fixture("pr_merge")
        obj["pr"]["head_sha"] = "a" * 39
        self.assertEqual(["pr.head_sha: must be a 40-character lowercase hex sha"], validate_request(obj))

    def test_a_complex_request_needs_chat_link_and_quote(self):
        """a complex request needs chat_link and quote"""
        obj = fixture("complex")
        del obj["chat_link"]
        del obj["quote"]
        self.assertEqual(["chat_link: is required for complex", "quote: is required for complex"], validate_request(obj))

    def test_a_time_without_an_offset_is_invalid(self):
        """a time without an offset is invalid"""
        obj = fixture("simple")
        obj["chase_at"] = "2026-01-05T10:00:00"
        self.assertEqual(["chase_at: must be an ISO 8601 string with an offset"], validate_request(obj))

    def test_chase_at_must_be_before_expires_at(self):
        """chase_at must be before expires_at"""
        obj = fixture("simple")
        obj["chase_at"] = "2026-01-05T11:00:00Z"
        obj["expires_at"] = "2026-01-05T10:00:00Z"
        self.assertEqual(["chase_at: must be before expires_at"], validate_request(obj))

    def test_cc_may_not_include_the_requester(self):
        """cc may not include the requester"""
        obj = fixture("simple")
        obj["cc"] = [obj["requester"]]
        self.assertEqual(["cc[0]: must not equal requester"], validate_request(obj))

    def test_an_integer_is_not_a_boolean(self):
        """an integer is not a boolean"""
        obj = fixture("pr_merge")
        obj["options"][1]["approves_merge"] = 1
        self.assertEqual(["options[1].approves_merge: must be a boolean"], validate_request(obj))

    def test_every_error_is_reported_not_just_the_first(self):
        """every error is reported, not just the first"""
        obj = fixture("simple")
        obj["title"] = "x" * 81
        obj["priority"] = "P9"
        obj["options"][1]["label"] = "C"
        self.assertEqual([
            "title: longer than 80 characters",
            "priority: must be one of P0, P1, P2",
            "options[1].label: must be B",
        ], validate_request(obj))

    def test_non_object_input_returns_an_error(self):
        self.assertEqual(["$: must be an object"], validate_request(None))

    def test_optional_collections_and_bounds_are_checked(self):
        obj = fixture("simple")
        obj.update({"bounds": {"other": "x"}, "links": ["http://example.com"], "depends_on": [1, 1], "supersedes": True})
        self.assertEqual([
            "bounds.other: unknown field",
            "links[0]: must start with https://",
            "depends_on[1]: must be distinct",
            "supersedes: must be an integer greater than or equal to 1",
        ], validate_request(obj))

    def test_required_fields_and_option_shapes_are_checked(self):
        obj = fixture("simple")
        obj.pop("question")
        obj["options"][0]["text"] = ""
        self.assertEqual(["question: is required", "options[0].text: must be at least 1 character(s)"], validate_request(obj))

    def test_pr_and_complex_only_fields_are_restricted(self):
        obj = fixture("simple")
        obj["pr"] = {}
        obj["chat_link"] = "https://example.com/decide"
        self.assertEqual(["chat_link: only allowed for complex", "pr: only allowed for pr_merge"], validate_request(obj))


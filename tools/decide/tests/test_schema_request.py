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
        self.assertEqual(["<unknown field>: unknown field"], validate_request(obj))

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
            "bounds.<unknown field>: unknown field",
            "links[0]: must be a valid https URL",
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


    def test_rejects_unsafe_and_invalid_values(self):
        """unsafe and invalid request values are rejected"""
        cases = [
            ("simple", ("key",), "bad key"), ("simple", ("key",), "x" * 81),
            ("simple", ("title",), " "), ("simple", ("requester",), "bad"),
            ("simple", ("kind",), "bad"), ("simple", ("options",), []),
            ("simple", ("options", 0, "reversible"), "bad"),
            ("simple", ("options", 0, "rec"), 1),
            ("simple", ("options", 0, "text"), "x" * 61),
            ("simple", ("options", 0, "changes"), "x" * 201),
            ("simple", ("bounds",), []), ("simple", ("bounds",), {"time": "x" * 101}),
            ("simple", ("links",), ["https://example.com"] * 6),
            ("simple", ("links",), ["https://example.com/" + "x" * 300]),
            ("simple", ("depends_on",), 1), ("simple", ("depends_on",), [True]),
            ("simple", ("cc",), ["bad"]),
            ("simple", ("cc",), ["22222222-2222-4222-8222-222222222222"] * 2),
            ("complex", ("chat_link",), "https://"),
            ("complex", ("chat_link",), "https://example.com/" + "x" * 300),
            ("complex", ("quote",), "x" * 301),
            ("pr_merge", ("pr", "repo"), "-x/.."),
            ("pr_merge", ("pr", "number"), True),
            ("pr_merge", ("pr", "base"), "x" * 101),
            ("pr_merge", ("pr", "trailers"), ["A: " + "x" * 101]),
            ("pr_merge", ("pr", "base"), "--upload-pack=x"),
            ("pr_merge", ("pr", "merger"), "bad"),
            ("pr_merge", ("pr", "merge_method"), "bad"),
            ("pr_merge", ("pr", "trailers"), ["A: b\nB: c"]),
        ]
        for name, limit in (("question", 300), ("why_owner", 200), ("rec_reason", 150)):
            cases.append(("simple", (name,), "x" * (limit + 1)))
        for field in ("title", "question", "why_owner", "rec_reason"):
            for value in ("a\nb", "a\u202eb", "a\u200bb", " "):
                cases.append(("simple", (field,), value))
        for field in ("text", "changes"):
            cases.append(("simple", ("options", 0, field), "a\u200bb"))
        cases.extend([("simple", ("bounds",), {"time": "a\nb"}),
                      ("complex", ("quote",), "a\u202eb")])
        for value in ("https://", "https://example.com/a b", "https://example.com/a\nb", "https://example.com/]x"):
            cases.append(("simple", ("links",), [value]))
        for value in ("main..other", "main@{x", "main branch", "main\nx", "main~x", "main^x", "main:x", "main?x", "main*x", "main[x", "main\\x", "main/", "main.lock"):
            cases.append(("pr_merge", ("pr", "base"), value))
        for value in ("a/.", "a/..", "-a/repo", "a/../b"):
            cases.append(("pr_merge", ("pr", "repo"), value))
        expected = [['key: contains invalid characters'],
         ['key: longer than 80 characters'],
         ['title: must be at least 1 character(s)'],
         ['requester: must be a UUID'],
         ['kind: must be one of simple, complex, pr_merge'],
         ['options: must contain 2 to 4 items', 'options: must have exactly one recommended option'],
         ['options[0].reversible: must be one of yes, no, partly'],
         ['options[0].rec: must be a boolean', 'options: must have exactly one recommended option'],
         ['options[0].text: longer than 60 characters'],
         ['options[0].changes: longer than 200 characters'],
         ['bounds: must be an object'],
         ['bounds.time: longer than 100 characters'],
         ['links: must contain at most 5 items'],
         ['links[0]: longer than 300 characters'],
         ['depends_on: must be a list'],
         ['depends_on[0]: must be an integer greater than or equal to 1'],
         ['cc[0]: must be a UUID'],
         ['cc[1]: must be distinct'],
         ['chat_link: must be a valid https URL'],
         ['chat_link: longer than 300 characters'],
         ['quote: longer than 300 characters'],
         ['pr.repo: must be an owner/repository'],
         ['pr.number: must be an integer greater than or equal to 1'],
         ['pr.base: must be a valid git ref'],
         ['pr.trailers[0]: longer than 100 characters'],
         ['pr.base: must be a valid git ref'],
         ['pr.merger: must be owner or agent'],
         ['pr.merge_method: must be merge, squash or rebase'],
         ['pr.trailers[0]: must be a single trailer line'],
         ['question: longer than 300 characters'],
         ['why_owner: longer than 200 characters'],
         ['rec_reason: longer than 150 characters'],
         ['title: contains non-printable or invisible characters'],
         ['title: contains non-printable or invisible characters'],
         ['title: contains non-printable or invisible characters'],
         ['title: must be at least 1 character(s)'],
         ['question: contains non-printable or invisible characters'],
         ['question: contains non-printable or invisible characters'],
         ['question: contains non-printable or invisible characters'],
         ['question: must be at least 1 character(s)'],
         ['why_owner: contains non-printable or invisible characters'],
         ['why_owner: contains non-printable or invisible characters'],
         ['why_owner: contains non-printable or invisible characters'],
         ['why_owner: must be at least 1 character(s)'],
         ['rec_reason: contains non-printable or invisible characters'],
         ['rec_reason: contains non-printable or invisible characters'],
         ['rec_reason: contains non-printable or invisible characters'],
         ['rec_reason: must be at least 1 character(s)'],
         ['options[0].text: contains non-printable or invisible characters'],
         ['options[0].changes: contains non-printable or invisible characters'],
         ['bounds.time: contains non-printable or invisible characters'],
         ['quote: contains non-printable or invisible characters'],
         ['links[0]: must be a valid https URL'],
         ['links[0]: must be a valid https URL'],
         ['links[0]: must be a valid https URL'],
         ['links[0]: must be a valid https URL'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.base: must be a valid git ref'],
         ['pr.repo: must be an owner/repository'],
         ['pr.repo: must be an owner/repository'],
         ['pr.repo: must be an owner/repository'],
         ['pr.repo: must be an owner/repository']]
        for index, (name, path, value) in enumerate(cases):
            with self.subTest(name=name, path=path, value=value):
                obj = fixture(name)
                target = obj
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                self.assertEqual(expected[index], validate_request(obj))

    def test_required_and_unknown_nested_fields_and_equal_times(self):
        """required fields and time boundaries are enforced"""
        for container in ("options", "pr"):
            obj = fixture("pr_merge")
            target = obj[container][0] if container == "options" else obj[container]
            target["unknown\nfield"] = True
            target.pop("text" if container == "options" else "repo")
            errors = validate_request(obj)
            self.assertTrue(any("unknown field" in e for e in errors))
            self.assertTrue(any("is required" in e for e in errors))
            self.assertTrue(all("unknown\nfield" not in e for e in errors))
        obj = fixture("simple")
        obj.update(chase_at="2026-01-05T10:00:00Z", expires_at="2026-01-05T10:00:00Z")
        self.assertIn("chase_at: must be before expires_at", validate_request(obj))

    def test_normalized_lengths_and_uuid_end_anchor(self):
        """normalized text length and UUID boundaries are enforced"""
        from decide_schema import UUID_RE
        obj = fixture("simple")
        obj["title"] = "\ufb03" * 27
        self.assertTrue(validate_request(obj))
        self.assertIsNone(UUID_RE.match(obj["requester"] + "\n"))

    def test_option_count_boundary_is_independent(self):
        obj = fixture("simple")
        obj["options"] = obj["options"][:1]
        self.assertEqual(["options: must contain 2 to 4 items"], validate_request(obj))

    def test_git_ref_component_rules(self):
        for base in ("@", "/main", "main//next", ".hidden", "main/.hidden", "main.", "foo.lock/bar"):
            with self.subTest(base=base):
                obj = fixture("pr_merge")
                obj["pr"]["base"] = base
                self.assertEqual(["pr.base: must be a valid git ref"], validate_request(obj))

    def test_spoofing_and_review_boundaries(self):
        """spoofing and review boundaries are rejected"""
        for value in ("\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u2800", "\u3164", "\uffa0", "\u180b", "\ufe0f", "\U000e0100", "a\u2028b", "a\u2029b", "\ud800", "\ue000"):
            obj = fixture("simple")
            obj["title"] = value
            self.assertIn("title: contains non-printable or invisible characters", validate_request(obj))
        for value in ("https://a@b/", "https://a\\@b", "https://а.test", "https://a。b", "https://a:abc/", "https://a:99999/", "https://a/\"x", "https://a/'x", "https://a/`x", "https://a/<", "https://a/>", "https://a/[", "https://a/\u200b", "https://a/\x00"):
            obj = fixture("simple")
            obj["links"] = [value]
            self.assertIn("links[0]: must be a valid https URL", validate_request(obj))
        for value in ("HEAD", "FETCH_HEAD", "refs/heads/main", "refs/pull/1/head", "mаin", "main\u034f", "main\u200b"):
            obj = fixture("pr_merge")
            obj["pr"]["base"] = value
            self.assertEqual(["pr.base: must be a valid git ref"], validate_request(obj))
        for value in ("A: b\rC: d", "A: b\x00", "A: b\x1b", "A: b\vC: d", "A: b\fC: d", "A: b\x1cC: d", "A: b\x85C: d", "A: b\u2028C: d", "A: b\u2029C: d", "A: \u202e", "A:  ", "1: b"):
            obj = fixture("pr_merge")
            obj["pr"]["trailers"] = [value]
            self.assertIn("pr.trailers[0]: must be a single trailer line", validate_request(obj))
        for value, message in (("bad", "pr.trailers: must be a list"), ([1], "pr.trailers[0]: must be a string")):
            obj = fixture("pr_merge")
            obj["pr"]["trailers"] = value
            self.assertEqual([message], validate_request(obj))
        for value in (0, True, "1"):
            obj = fixture("pr_merge")
            obj["pr"]["merge_order"] = value
            self.assertEqual(["pr.merge_order: must be an integer greater than or equal to 1"], validate_request(obj))
        for field in ("text", "changes"):
            obj = fixture("simple")
            obj["options"][0][field] = "  "
            self.assertEqual(["options[0]." + field + ": must be at least 1 character(s)"], validate_request(obj))
        obj = fixture("complex")
        obj["quote"] = "  "
        self.assertEqual(["quote: must be at least 1 character(s)"], validate_request(obj))
        obj = fixture("pr_merge")
        obj["pr"]["head_sha"] = "A" * 40
        self.assertEqual(["pr.head_sha: must be a 40-character lowercase hex sha"], validate_request(obj))
        for container, field, message in (("pr", "merge_method", "pr.merge_method: is required"), ("option", "rec", "options[1].rec: is required")):
            obj = fixture("pr_merge")
            del (obj["pr"] if container == "pr" else obj["options"][1])[field]
            self.assertEqual([message], validate_request(obj))
        for length in (300, 301):
            obj = fixture("simple")
            obj["links"] = ["https://a/" + "x" * (length - 10)]
            self.assertEqual([] if length == 300 else ["links[0]: longer than 300 characters"], validate_request(obj))
        for length in (100, 101):
            obj = fixture("pr_merge")
            obj["pr"]["trailers"] = ["A: " + "x" * (length - 3)]
            self.assertEqual([] if length == 100 else ["pr.trailers[0]: longer than 100 characters"], validate_request(obj))
        for length in (39, 40):
            obj = fixture("pr_merge")
            obj["pr"]["repo"] = "a" * length + "/b"
            self.assertEqual([] if length == 39 else ["pr.repo: must be an owner/repository"], validate_request(obj))
        for value in (0, 1):
            obj = fixture("simple")
            obj["supersedes"] = value
            self.assertEqual([] if value else ["supersedes: must be an integer greater than or equal to 1"], validate_request(obj))

    def test_owner_can_merge(self):
        obj = fixture("pr_merge")
        obj["pr"]["merger"] = "owner"
        self.assertEqual([], validate_request(obj))

    def test_unknown_fields_are_redacted(self):
        for container in ("root", "bounds", "options", "pr"):
            obj = fixture("pr_merge")
            if container == "bounds":
                obj["bounds"] = {}
            target = obj if container == "root" else obj[container]
            if container == "options":
                target = target[0]
            target["sensitive\nfield"] = True
            errors = validate_request(obj)
            self.assertTrue(any("unknown field" in error for error in errors))
            self.assertTrue(all("sensitive" not in error for error in errors))

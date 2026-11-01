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

    def test_raw_text_length_is_limited_before_normalization(self):
        """raw text length is limited before normalization"""
        obj = fixture("simple")
        obj["title"] = "e\u0301" * 41
        self.assertEqual(validate_request(obj), ["title: longer than 80 characters"])

    def test_option_count_boundary_is_independent(self):
        """option count boundary is independent"""
        obj = fixture("simple")
        obj["options"] = obj["options"][:1]
        self.assertEqual(["options: must contain 2 to 4 items"], validate_request(obj))

    def test_git_ref_component_rules(self):
        """git ref component rules are enforced"""
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
            obj["links"] = ["https://a.test/" + "x" * (length - 15)]
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
        """owner can merge"""
        obj = fixture("pr_merge")
        obj["pr"]["merger"] = "owner"
        self.assertEqual([], validate_request(obj))

    def test_unknown_fields_are_redacted(self):
        """unknown fields are redacted"""
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

    def test_raw_text_and_authority_boundaries(self):
        """raw text and authority boundaries are enforced"""
        for value in ("https://a%2eb/", "https://%61.b/", "https://0x7f000001/", "https://127.1/", "https://127.0.0.1/", "https://a..b/", "https://-a.b/", "https://:80/", "https://a\\.b/", "https://a:80%30/"):
            with self.subTest(value=value):
                obj = fixture("simple")
                obj["links"] = [value]
                self.assertIn("links[0]: must be a valid https URL", validate_request(obj))
        for value in ("\u180f", "\ufe00", "\U000e01ef", "\u0301" * 5, "a" + "\u0301" * 79):
            with self.subTest(value=value):
                obj = fixture("simple")
                obj["title"] = value
                self.assertTrue(validate_request(obj))
        obj = fixture("simple")
        obj["title"] = "\u03b1\u0314\u0342\u0345" * 80
        self.assertIn("title: longer than 80 characters", validate_request(obj))
        for value in ("A: \u3164", "A: \u2800", "A: x\u034f"):
            with self.subTest(value=value):
                obj = fixture("pr_merge")
                obj["pr"]["trailers"] = [value]
                self.assertIn("pr.trailers[0]: must be a single trailer line", validate_request(obj))
        obj = fixture("pr_merge")
        obj["pr"]["trailers"] = ["A: " + "\ufb03" * 33]
        self.assertIn("pr.trailers[0]: longer than 100 characters", validate_request(obj))
        obj = fixture("pr_merge")
        obj["pr"]["base"] = "-x"
        self.assertEqual(["pr.base: must be a valid git ref"], validate_request(obj))

    def test_review_boundaries(self):
        """review boundaries are enforced"""
        for host in ("0x", "0x.0x", "0x7f.0x", "1.0x", "localhost", "intranet", "a.1", "example.123", "a.0x", "a" * 64 + ".test"):
            obj = fixture("simple")
            obj["links"] = ["https://" + host + "/"]
            self.assertEqual(["links[0]: must be a valid https URL"], validate_request(obj), host)
        obj = fixture("simple")
        obj["links"] = ["https://" + "a" * 63 + ".test/"]
        self.assertEqual([], validate_request(obj))
        for path in ("/é", "/a\\b"):
            obj = fixture("simple")
            obj["links"] = ["https://example.test" + path]
            self.assertEqual(["links[0]: must be a valid https URL"], validate_request(obj), path)
        for char in ("\u180b", "\u180f", "\ufe00", "\ufe0f", "\U000e0100", "\U000e01ef", "\u17b4", "\u17b5", "\U00016fe4", "\U0001d159", "\ufffc"):
            obj = fixture("simple")
            obj["title"] = "a" + char
            self.assertEqual(["title: contains non-printable or invisible characters"], validate_request(obj), repr(char))
        for value in ("\u0301abc", "a" + "\u0301" * 3, "a" + "\u20dd" * 3, "\u0301\u0301", " \u0301\u0301"):
            obj = fixture("simple")
            obj["title"] = value
            self.assertEqual(["title: contains non-printable or invisible characters"], validate_request(obj), repr(value))
        for value in ("a\u0301\u0301", "a\u0301\u0301b\u0301\u0301", "a\u00a0b", "a\u3000b", "a👩\u200d💻", "a❤\ufe0f", "a❤\ufe0f\u200d🔥", "aשָּׁ"):
            obj = fixture("simple")
            obj["title"] = value
            self.assertEqual([], validate_request(obj), repr(value))
        for value in ("\u0301\u0301", "\U00016fe4", "\U0001d159", "\ufffc"):
            obj = fixture("pr_merge")
            obj["pr"]["trailers"] = ["A: " + value]
            self.assertEqual(["pr.trailers[0]: must be a single trailer line"], validate_request(obj), repr(value))
        obj = fixture("pr_merge")
        obj["pr"]["trailers"] = ["A: " + "e\u0301" * 49]
        self.assertEqual(["pr.trailers[0]: longer than 100 characters"], validate_request(obj))
        obj = fixture("simple")
        obj["options"] += [dict(obj["options"][1], label=label) for label in ("C", "D", "E")]
        self.assertEqual(["options: must contain 2 to 4 items", "options[4].label: must be a valid label"], validate_request(obj))
        for field in ("cc", "depends_on", "trailers"):
            obj = fixture("pr_merge")
            values = (["00000000-0000-0000-0000-%012d" % i for i in range(1, 22)] if field == "cc" else list(range(1, 22)) if field == "depends_on" else ["A: x"] * 21)
            (obj["pr"] if field == "trailers" else obj)[field] = values
            self.assertEqual([("pr." if field == "trailers" else "") + field + ": must contain at most 20 items"], validate_request(obj))

    def test_mutation_boundaries_are_enforced(self):
        """mutation boundaries are enforced"""
        for char in ("\u180a", "\u1810", "\ufdff", "\ufe10"):
            obj = fixture("simple")
            obj["title"] = "a" + char
            self.assertEqual([], validate_request(obj), repr(char))
        for value in (None, 1):
            obj = fixture("simple")
            obj["key"] = value
            self.assertEqual(["key: must be a string"], validate_request(obj))
        for value in ("x", "x" * 80, "ﬁ" * 40, "x" * 81, "ﬁ" * 41):
            obj = fixture("simple")
            obj["title"] = value
            self.assertEqual([] if len(value) <= 80 and len(value.replace("ﬁ", "fi")) <= 80 else ["title: longer than 80 characters"], validate_request(obj))
        for value in ("א\u0591\u0301\u0301", "א\u05c7\u0301\u0301"):
            obj = fixture("simple")
            obj["title"] = value
            self.assertEqual([], validate_request(obj))
        for value in ("\ufb29\u0591", "\u0903", "a\u0591", "ж\u0591", "a" + ("\u0301\u0301\u0591" * 26), "a" + "\u0591" * 79, "a \u0301\u0301", "א" + "\u0591" * 5, "a👩\u200dx", "א\u0591\u0301\u0301\u0591\u0301"):
            obj = fixture("simple")
            obj["title"] = value
            self.assertEqual(["title: contains non-printable or invisible characters"], validate_request(obj), repr(value))
        for value in ("123", "?", "\u05be", " \u05c0 ", " \u05c3", "\u05c6", "a\u05be", "\u05ef\u05b7", "\u05f2\u05b7", "\u05d0\u05b8\u05b8\u05b8\u05d1\u05b8\u05b8", "א" + "\u0591" * 4, "א\u05c7", "\ufb1d\u0591", "\u05ea\u0591", "\ufb4f\u0591", "א\u0301\u0591\u0301"):
            obj = fixture("simple")
            obj["title"] = value
            self.assertEqual([], validate_request(obj), repr(value))
        for value in ("https://user@example.test/", "https://example.test:99999/", "https://example.test:abc/", "https://example.test/\"x", "https://example.test/'x", "https://example.test/`x"):
            obj = fixture("simple")
            obj["links"] = [value]
            self.assertEqual(["links[0]: must be a valid https URL"], validate_request(obj), value)
        for value in ("👩\u200d💻", "👩\u200d", "a\u200d💻"):
            obj = fixture("simple")
            obj["title"] = value
            self.assertEqual([] if value == "👩\u200d💻" else ["title: contains non-printable or invisible characters"], validate_request(obj))
        for count in (3, 4):
            obj = fixture("simple")
            obj["options"] += [dict(obj["options"][1], label=label) for label in ("C", "D")[:count - 2]]
            self.assertEqual([], validate_request(obj))
        for field in ("cc", "depends_on", "trailers", "links"):
            obj = fixture("pr_merge")
            count = 5 if field == "links" else 20
            values = (["00000000-0000-0000-0000-%012d" % i for i in range(1, count + 1)] if field == "cc" else list(range(1, count + 1)) if field == "depends_on" else ["A: x"] * count if field == "trailers" else [fixture("complex")["chat_link"]] * count)
            (obj["pr"] if field == "trailers" else obj)[field] = values
            self.assertEqual([], validate_request(obj), field)
        for length in (1, 99, 100, 101):
            obj = fixture("pr_merge")
            obj["pr"]["base"] = "x" * length
            self.assertEqual([] if length <= 100 else ["pr.base: must be a valid git ref"], validate_request(obj))
        for length in (99, 100, 101):
            obj = fixture("pr_merge")
            obj["pr"]["trailers"] = ["A: " + "x" * (length - 3)]
            self.assertEqual([] if length <= 100 else ["pr.trailers[0]: longer than 100 characters"], validate_request(obj))
        obj = fixture("pr_merge")
        obj["pr"]["trailers"] = ["A: " + "ﬃ" * 32 + "xx"]
        self.assertEqual(["pr.trailers[0]: longer than 100 characters"], validate_request(obj))
        obj = fixture("simple")
        obj["bounds"] = {"time": ""}
        self.assertEqual([], validate_request(obj))
        obj["bounds"] = {"time": "ﬁ" * 50 + " "}
        self.assertEqual(["bounds.time: longer than 100 characters"], validate_request(obj))

    def test_unreached_validator_branches_are_rejected(self):
        """unreached validator branches return their exact errors"""
        missing = object()
        cases = [
            ("simple", ("requester",), missing, "requester: is required"),
            ("simple", ("kind",), missing, "kind: is required"),
            ("simple", ("priority",), missing, "priority: is required"),
            ("simple", ("options",), missing, "options: is required"),
            ("simple", ("options",), "string", "options: must be a list"),
            ("simple", ("options", 1), 1, "options[1]: must be an object"),
            ("simple", ("options", 1, "label"), missing, "options[1].label: is required"),
            ("simple", ("options", 1, "reversible"), missing, "options[1].reversible: is required"),
            ("simple", ("options", 1, "unknown"), True, "options[1].<unknown field>: unknown field"),
            ("simple", ("links", 0), 1, "links[0]: must be a string"),
            ("simple", ("links",), "string", "links: must be a list"),
            ("simple", ("cc", 0), [], "cc[0]: must be a UUID"),
            ("simple", ("cc",), "string", "cc: must be a list"),
            ("simple", ("depends_on", 0), [1], "depends_on[0]: must be an integer greater than or equal to 1"),
            ("simple", ("chase_at",), 1, "chase_at: must be an ISO 8601 string with an offset"),
            ("simple", ("bounds", "milestone"), 1, "bounds.milestone: must be a string"),
            ("simple", ("bounds", "spend"), 1, "bounds.spend: must be a string"),
            ("pr_merge", ("pr",), missing, "pr: is required for pr_merge"),
            ("pr_merge", ("pr",), [], "pr: must be an object"),
            ("pr_merge", ("pr", "unknown"), True, "pr.<unknown field>: unknown field"),
            ("pr_merge", ("pr", "base"), missing, "pr.base: is required"),
            ("pr_merge", ("pr", "merge_method"), "squash", None),
            ("pr_merge", ("pr", "merge_method"), "rebase", None),
        ]
        for name, path, value, expected in cases:
            with self.subTest(name=name, path=path, value=value):
                obj = fixture(name)
                if path[0] in ("links", "depends_on"):
                    obj.setdefault(path[0], [])
                elif path[0] == "bounds":
                    obj.setdefault("bounds", {})
                target = obj
                for part in path[:-1]:
                    target = target[part]
                if value is missing:
                    del target[path[-1]]
                elif path[-1] == "unknown":
                    target["unknown"] = value
                elif isinstance(target, list) and path[-1] == len(target):
                    target.append(value)
                else:
                    target[path[-1]] = value
                self.assertEqual([] if expected is None else [expected], validate_request(obj))

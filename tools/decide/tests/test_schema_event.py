import unittest

from decide_schema import UUID_RE, validate_answer, validate_event, validate_legacy


def event(**changes):
    value = {"seq": 1, "ts": "2026-01-05T12:00:00Z", "type": "ask", "id": 1, "data": {}, "prev_sha256": "0" * 64}
    value.update(changes)
    return value


def answer(**changes):
    value = {"choice": "A", "label": "A", "words": "yes", "via": "chat", "msg_ref": "ref", "mapped_by": "token", "closes": [], "recorded_by": "record"}
    value.update(changes)
    return value


class EventSchemaTests(unittest.TestCase):
    def test_an_event_with_an_unknown_type_is_invalid(self):
        """an event with an unknown type is invalid"""
        self.assertEqual(validate_event(event(type="unknown")), ["type: must be a known event type"])

    def test_only_page_ack_and_counter_floor_may_have_a_null_id(self):
        """only page_ack and counter_floor may have a null id"""
        self.assertEqual(validate_event(event(id=None)), ["id: must be a positive integer or null for page_ack/counter_floor"])
        self.assertEqual(validate_event(event(type="page_ack", id=None)), [])
        self.assertEqual(validate_event(event(type="counter_floor", id=None)), [])

    def test_prev_sha256_must_be_64_hex_characters(self):
        """prev_sha256 must be 64 hex characters"""
        self.assertEqual(validate_event(event(prev_sha256="A" * 64)), ["prev_sha256: must be 64 lowercase hex characters"])

    def test_an_event_timestamp_must_be_utc_with_z(self):
        """an event timestamp must be UTC with Z"""
        self.assertEqual(validate_event(event(ts="2026-01-05T12:00:00+00:00")), ["ts: must be a UTC timestamp ending in Z"])

    def test_an_answer_with_an_invalid_recorder_is_invalid(self):
        """an answer with an invalid recorder is invalid"""
        self.assertEqual(validate_answer(answer(recorded_by="invalid")), ["recorded_by: must be record"])

    def test_a_judgement_mapping_cannot_be_custom(self):
        """a judgement mapping cannot be custom"""
        self.assertEqual(validate_answer(answer(choice="custom", label=None, mapped_by="judgement")), ["mapped_by: judgement cannot map custom"])

    def test_blank_words_are_invalid(self):
        """blank words are invalid"""
        self.assertEqual(validate_answer(answer(words="  \t")), ["words: must contain 1 to 4000 non-blank characters"])

    def test_closes_ids_must_be_distinct(self):
        """closes ids must be distinct"""
        closes = [{"id": 1, "choice": "A"}, {"id": 1, "choice": "B"}]
        self.assertEqual(validate_answer(answer(closes=closes)), ["closes[1].id: must be distinct"])

    def test_a_legacy_record_needs_only_id_kind_title_and_state(self):
        """a legacy record needs only id kind title and state"""
        self.assertEqual(validate_legacy({"id": 1, "kind": "simple", "title": "Legacy", "state": "open"}), [])
        self.assertEqual(validate_legacy({"kind": "simple", "title": "Legacy", "state": "open"}), ["id: is required"])

    def test_a_legacy_short_head_sha_is_allowed(self):
        """a legacy short head sha is allowed"""
        self.assertEqual(validate_legacy({"id": 1, "kind": "pr_merge", "title": "Legacy", "state": "merged", "pr": {"head_sha": "abcdef0"}}), [])
        self.assertEqual(validate_legacy({"id": 1, "kind": "pr_merge", "title": "Legacy", "state": "merged", "pr": {"head_sha": "abcdef"}}), ["pr.head_sha: must be 7 to 40 lowercase hex characters"])

    def test_free_text_rejects_unsafe_characters_and_uses_normalized_length(self):
        """free text rejects unsafe characters and uses normalized length"""
        legacy = {"id": 1, "kind": "simple", "title": "Legacy", "state": "open"}
        for value in ("line\nfeed", "bidi\u202e", "zero\u200b"):
            with self.subTest(value=value):
                self.assertTrue(validate_answer(answer(words=value)))
                self.assertTrue(validate_answer(answer(msg_ref=value)))
                self.assertTrue(validate_legacy(dict(legacy, title=value)))
        self.assertTrue(validate_legacy(dict(legacy, title="   ")))
        self.assertTrue(validate_answer(answer(words="ﬃ" * 1334)))
        self.assertTrue(validate_answer(answer(msg_ref="ﬃ" * 67)))
        self.assertEqual(validate_answer(answer(words="café", msg_ref="réf")), [])

    def test_validation_rejects_invalid_boundaries(self):
        """validation rejects invalid boundaries"""
        legacy = {"id": 1, "kind": "simple", "title": "Legacy", "state": "open"}
        for timestamp in ("2026-13-05T12:00:00Z", "2026-01-05T99:00:00Z", "２０２６-01-05T12:00:00Z"):
            self.assertEqual(validate_event(event(ts=timestamp)), ["ts: must be a UTC timestamp ending in Z"])
        self.assertEqual(validate_event(event(id=0)), ["id: must be a positive integer or null for page_ack/counter_floor"])
        self.assertEqual(validate_event(event(prev_sha256="0" * 63)), ["prev_sha256: must be 64 lowercase hex characters"])
        self.assertEqual(validate_answer(answer(mapped_by="judgement")), [])
        self.assertEqual(validate_answer(answer(choice="custom", label="A")), ["label: must be a label or null for custom"])
        self.assertEqual(validate_answer(answer(closes=[{"id": True, "choice": "A"}])), ["closes[0].id: must be a positive integer"])
        self.assertEqual(validate_legacy(dict(legacy, id=True)), ["id: must be an integer greater than or equal to 1"])
        for value in ("bad", []):
            self.assertEqual(validate_legacy(dict(legacy, pr=value)), ["pr: must be an object"])
        for field, limit in (("words", 4000), ("msg_ref", 200)):
            self.assertEqual(validate_answer(answer(**{field: "x" * limit})), [])
            self.assertEqual(validate_answer(answer(**{field: "x" * (limit + 1)})), ["{}: must contain 1 to {} {}characters".format(field, limit, "non-blank " if field == "words" else "")])
        self.assertEqual(validate_answer(answer(words="\ud800")), ["words: must contain 1 to 4000 non-blank characters"])
        self.assertEqual(validate_legacy(dict(legacy, title="\ud800")), ["title: must be a non-empty string"])

    def test_event_and_answer_boundaries(self):
        """event and answer boundaries are enforced"""
        try:
            errors = validate_event(event(ts=1))
        except TypeError:
            self.fail("non-string timestamp must return a validation error")
        self.assertEqual(errors, ["ts: must be a UTC timestamp ending in Z"])
        self.assertEqual(validate_event(event(id=True)), ["id: must be a positive integer or null for page_ack/counter_floor"])
        self.assertEqual(validate_answer(answer(via="card")), [])
        self.assertEqual(validate_answer(answer(closes=[{"id": 1, "choice": "custom"}])), ["closes[0].choice: must be a label"])
        self.assertEqual(validate_answer(answer(closes="")), ["closes: must be a list"])
        legacy = {"id": 1, "kind": "simple", "title": "Legacy", "state": "open", "pr": {"head_sha": "a" * 41}}
        self.assertEqual(validate_legacy(legacy), ["pr.head_sha: must be 7 to 40 lowercase hex characters"])

    def test_free_text_rejects_invisible_and_overlong_raw_values(self):
        """free text rejects invisible and overlong raw values"""
        legacy = {"id": 1, "kind": "simple", "title": "Legacy", "state": "open"}
        for value in ("\ue000", "\ufffe", "\uffff", "\u0378", "\u3164", "\u115f", "\u2800", "\u0301"):
            with self.subTest(value=value):
                self.assertEqual(validate_answer(answer(words=value)), ["words: must contain 1 to 4000 non-blank characters"])
        self.assertEqual(validate_answer(answer(words="e\u0301" * 2001)), ["words: must contain 1 to 4000 non-blank characters"])
        self.assertEqual(validate_legacy(dict(legacy, title="x" * 81)), ["title: must be a non-empty string"])

    def test_free_text_requires_strings(self):
        """free text requires strings"""
        legacy = {"id": 1, "kind": "simple", "title": "Legacy", "state": "open"}
        try:
            for field in ("words", "msg_ref"):
                self.assertEqual(len(validate_answer(answer(**{field: 1}))), 1)
            self.assertEqual(validate_legacy(dict(legacy, title=1)), ["title: must be a non-empty string"])
        except (TypeError, AttributeError):
            self.fail("non-string text must return a validation error")

    def test_invalid_choice_and_label_report_both_errors(self):
        """invalid choice and label report both errors"""
        self.assertEqual(validate_answer(answer(choice="X", label="X")), [
            "choice: must be a label or custom",
            "label: must be a label or null for custom",
        ])

    def test_raw_non_printable_text_is_rejected_after_normalization(self):
        """raw non printable text is rejected after normalization"""
        self.assertEqual(validate_answer(answer(words="a\u00a0")),
                         ["words: must contain 1 to 4000 non-blank characters"])

    def test_unknown_fields_do_not_echo_input(self):
        """unknown fields do not echo input"""
        for validator, value in ((validate_event, event()), (validate_answer, answer())):
            value["secret\nforged"] = 1
            self.assertEqual(validator(value), ["$: unknown field"])

    def test_identifiers_reject_trailing_newlines(self):
        """identifiers reject trailing newlines"""
        legacy = {"id": 1, "kind": "simple", "title": "Legacy", "state": "open"}
        self.assertTrue(validate_event(event(ts="2026-01-05T12:00:00Z\n")))
        self.assertTrue(validate_event(event(prev_sha256="0" * 64 + "\n")))
        self.assertIsNone(UUID_RE.match("12345678-1234-1234-1234-123456789abc\n"))
        self.assertTrue(validate_legacy(dict(legacy, requester="12345678-1234-1234-1234-123456789abc\n")))
        self.assertTrue(validate_legacy(dict(legacy, pr={"head_sha": "abcdef0\n"})))

    def test_event_envelope_rejects_invalid_fields(self):
        for changes in ({"seq": 0}, {"seq": True}, {"data": []}):
            with self.subTest(changes=changes):
                self.assertTrue(validate_event(event(**changes)))
        for field in event():
            value = event()
            del value[field]
            self.assertTrue(validate_event(value), field)
        self.assertTrue(validate_event([]))

    def test_answer_rejects_invalid_fields(self):
        cases = (
            {"choice": "X"}, {"choice": "custom", "label": "X"}, {"label": "B"},
            {"via": "other"}, {"mapped_by": "other"}, {"closes": {}},
            {"closes": [None]}, {"closes": [{"id": 1, "choice": "A", "extra": 1}]},
            {"closes": [{"id": 0, "choice": "A"}]},
            {"closes": [{"id": 1, "choice": "X"}]},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertTrue(validate_answer(answer(**changes)))
        for field in answer():
            value = answer()
            del value[field]
            self.assertTrue(validate_answer(value), field)
        self.assertTrue(validate_answer([]))

    def test_legacy_rejects_invalid_required_fields(self):
        legacy = {"id": 1, "kind": "simple", "title": "Legacy", "state": "open"}
        for field in legacy:
            value = dict(legacy)
            del value[field]
            self.assertTrue(validate_legacy(value), field)
        for changes in ({"id": 0}, {"kind": "unknown"}, {"state": "unknown"}):
            with self.subTest(changes=changes):
                self.assertTrue(validate_legacy(dict(legacy, **changes)))
        self.assertTrue(validate_legacy([]))

if __name__ == "__main__":
    unittest.main()

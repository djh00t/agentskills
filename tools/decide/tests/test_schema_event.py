import unittest

from decide_schema import CLOSED_STATES, STATES, UUID_RE, validate_answer, validate_event, validate_legacy


def event(**changes):
    value = {"seq": 1, "ts": "2026-01-05T12:00:00Z", "type": "ask", "id": 1, "data": {}, "prev_sha256": "0" * 64}
    value.update(changes)
    return value


def answer(**changes):
    value = {"choice": "A", "label": "A", "words": "yes", "via": "chat", "msg_ref": "ref", "mapped_by": "token", "closes": [], "recorded_by": "decisions"}
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

    def test_an_answer_recorded_by_anyone_but_decisions_is_invalid(self):
        """an answer recorded by anyone but decisions is invalid"""
        self.assertEqual(validate_answer(answer(recorded_by="operator")), ["recorded_by: must be decisions"])

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

    def test_closed_states_are_exactly_the_seven_terminal_states(self):
        """closed states are exactly the seven terminal states"""
        self.assertEqual(CLOSED_STATES, frozenset({"answered", "rejected", "merged", "merge_failed", "expired", "withdrawn", "superseded"}))
        self.assertEqual(len(STATES) - len(CLOSED_STATES), 5)


if __name__ == "__main__":
    unittest.main()

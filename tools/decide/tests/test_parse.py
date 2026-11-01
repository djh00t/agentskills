import unittest

from decide_parse import parse_text


class ParseTextTests(unittest.TestCase):
    def test_reviewed_parser_spellings(self):
        for text, result, item_id, choice in (
            ("152 B", "option", 152, "B"),
            ("152  B", "option", 152, "B"),
            ("152: b", "option", 152, "B"),
            ("152: d", "option", 152, "D"),
            ("152 : B", "option", 152, "B"),
            ("152: B,reason", "option", 152, "B"),
            (": B", "ambiguous", None, None),
            ("# B", "ambiguous", None, None),
            ("approve #", "ambiguous", None, None),
            ("approve #7", "option", 7, "rec"),
            ("approve  7", "option", 7, "rec"),
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_text(text), {
                    "result": result, "id": item_id, "choice": choice, "words": text,
                })

    def test_approval_requires_a_separator(self):
        """approval requires a separator"""
        self.assertEqual(parse_text("approve7"), {
            "result": "ambiguous", "id": None, "choice": None, "words": "approve7",
        })

    def test_bounds_invisibles_and_answer_contract(self):
        """bounded and safe answer text"""
        for text in ("1" * 4001, "1" * 4301, "1" * 20000, "\ufdfa" * 223):
            self.assertEqual(parse_text(text)["result"], "ambiguous")
        for text in ("152: B\u3164", "152\u3164: B"):
            self.assertEqual((parse_text(text)["result"], parse_text(text)["id"], parse_text(text)["choice"]), ("option", 152, "B"))
        for text in ("152: B\nmore", "152: B\x07"):
            self.assertEqual(parse_text(text), {"result": "ambiguous", "id": None, "choice": None, "words": text})
        self.assertEqual(parse_text("123456789: B")["id"], 123456789)
        for text in ("1234567890: B", "١٥٢: B"):
            self.assertNotEqual(parse_text(text)["result"], "option")
        self.assertEqual(parse_text("152: B, 3 apples")["result"], "option")
        self.assertEqual(parse_text("Approve 7")["choice"], "rec")

    def test_review_regressions(self):
        for char in ("\u115f", "\u1160", "\u17b4", "\u17b5", "\uffa0", "\U00016fe4", "\U0001d159", "\ufffc"):
            with self.subTest(char=char):
                self.assertEqual(parse_text("152: B" + char), {
                    "result": "option", "id": 152, "choice": "B", "words": "152: B",
                })
        for text, result, item_id, choice in (
            ("1234567890 B", "ambiguous", None, None),
            ("approve 1234567890", "ambiguous", None, None),
            ("see #1234567890", "ambiguous", None, None),
            ("1: A, 12345678901 B", "option", 1, "A"),
            ("1: A, 1234567890 B", "option", 1, "A"),
            ("152: B\n", "ambiguous", None, None),
            ("152: B, ok?\n\nthanks", "question", 152, None),
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_text(text), {
                    "result": result, "id": item_id, "choice": choice, "words": text,
                })

    def test_invisible_range_boundaries_after_a_letter(self):
        for code in (0x180A, 0x180B, 0x180F, 0x1810,
                     0xFDFF, 0xFE00, 0xFE0F, 0xFE10,
                     0xE00FF, 0xE0100, 0xE01EF, 0xE01F0):
            char = chr(code)
            with self.subTest(code=hex(code)):
                text = "1: A, x" + char
                result = parse_text(text)
                if code in (0x180B, 0x180F, 0xFE00, 0xFE0F, 0xE0100, 0xE01EF):
                    self.assertEqual(result["words"], "1: A, x")
                else:
                    self.assertEqual(result["words"], text)

    def test_length_limits_at_boundaries(self):
        for length in (3999, 4000, 4001):
            text = "1: A, " + "x" * (length - 6)
            with self.subTest(length=length):
                self.assertEqual(parse_text(text)["result"], "option" if length <= 4000 else "ambiguous")
        text = "1: A, " + "x" * 3993 + "e\u0301"
        self.assertEqual(len(text), 4001)
        self.assertEqual(parse_text(text)["result"], "ambiguous")
        for length in (3999, 4000, 4001):
            text = "1: A, " + "x" * (length - 8) + "\ufb00"
            with self.subTest(normalized_length=length):
                self.assertEqual(parse_text(text)["result"], "option" if length <= 4000 else "ambiguous")

    def test_character_validation_and_id_boundaries(self):
        for text, result, item_id in (("123456789: A", "option", 123456789),
                                      ("1234567890: A", "ambiguous", None),
                                      ("1: A, plain 2", "option", 1),
                                      ("1: A, digit ٢", "ambiguous", None),
                                      ("1: A, letter", "option", 1),
                                      ("\u0301", "ambiguous", None)):
            with self.subTest(text=text):
                parsed = parse_text(text)
                self.assertEqual((parsed["result"], parsed["id"]), (result, item_id))

    def test_a_widget_tap_is_an_option(self):
        """a widget tap is an option"""
        self.assertEqual(parse_text("152: B, Keep the old layout"), {
            "result": "option", "id": 152, "choice": "B",
            "words": "152: B, Keep the old layout",
        })

    def test_a_bare_token_is_an_option(self):
        """a bare token is an option"""
        self.assertEqual(parse_text("126: A"), {
            "result": "option", "id": 126, "choice": "A", "words": "126: A",
        })

    def test_a_token_without_a_colon_is_an_option(self):
        """a token without a colon is an option"""
        self.assertEqual(parse_text("#9 c"), {
            "result": "option", "id": 9, "choice": "C", "words": "#9 c",
        })

    def test_a_token_with_a_reason_is_an_option(self):
        """a token with a reason is an option"""
        self.assertEqual(parse_text("152: B, move all of them"), {
            "result": "option", "id": 152, "choice": "B",
            "words": "152: B, move all of them",
        })

    def test_semicolon_reason_separator_is_an_option(self):
        """a semicolon reason separator is an option"""
        self.assertEqual(parse_text("152: B; reason"), {
            "result": "option", "id": 152, "choice": "B",
            "words": "152: B; reason",
        })

    def test_period_reason_separator_is_an_option(self):
        """a period reason separator is an option"""
        self.assertEqual(parse_text("152: B. reason"), {
            "result": "option", "id": 152, "choice": "B",
            "words": "152: B. reason",
        })

    def test_colon_reason_separator_is_an_option(self):
        """a colon reason separator is an option"""
        self.assertEqual(parse_text("152: B: reason"), {
            "result": "option", "id": 152, "choice": "B",
            "words": "152: B: reason",
        })

    def test_hyphen_reason_separator_is_an_option(self):
        """a hyphen reason separator is an option"""
        self.assertEqual(parse_text("152: B - reason"), {
            "result": "option", "id": 152, "choice": "B",
            "words": "152: B - reason",
        })

    def test_hash_prefixed_option_is_an_option(self):
        """a hash prefixed option is an option"""
        self.assertEqual(parse_text("#152: B"), {
            "result": "option", "id": 152, "choice": "B", "words": "#152: B",
        })

    def test_id_without_a_separator_is_ambiguous(self):
        """an id without a separator is ambiguous"""
        self.assertEqual(parse_text("152B"), {
            "result": "ambiguous", "id": None, "choice": None, "words": "152B",
        })

    def test_stripped_question_text_keeps_its_id(self):
        """stripped question text keeps its id"""
        self.assertEqual(parse_text("  152: B?"), {
            "result": "question", "id": 152, "choice": None, "words": "  152: B?",
        })

    def test_normalized_question_id_keeps_its_id(self):
        """normalized question id keeps its id"""
        self.assertEqual(parse_text("\uff03152?"), {
            "result": "question", "id": 152, "choice": None, "words": "\uff03152?",
        })

    def test_full_width_option_is_normalized(self):
        """a full-width option is normalized"""
        text = "152：Ｂ"
        self.assertEqual(parse_text(text), {
            "result": "option", "id": 152, "choice": "B", "words": text,
        })

    def test_invisible_character_is_removed_from_option(self):
        """an invisible character is removed from an option"""
        text = "152: B\u200b"
        self.assertEqual(parse_text(text), {
            "result": "option", "id": 152, "choice": "B", "words": "152: B",
        })

    def test_question_id_is_found_after_normalization(self):
        """a question id is found after normalization"""
        text = "\u200b152: B?"
        self.assertEqual(parse_text(text), {
            "result": "question", "id": 152, "choice": None, "words": "152: B?",
        })

    def test_question_takes_precedence_over_multiple_decisions(self):
        """a question takes precedence over multiple decisions"""
        text = "152: B? 153: A"
        self.assertEqual(parse_text(text), {
            "result": "question", "id": 152, "choice": None, "words": text,
        })

    def test_question_mark_in_reason_takes_precedence_over_option(self):
        """a question mark in a reason takes precedence over an option"""
        self.assertEqual(parse_text("152: B, is that ok?"), {
            "result": "question", "id": 152, "choice": None,
            "words": "152: B, is that ok?",
        })

    def test_full_width_question_mark_is_a_question(self):
        """a full-width question mark is a question"""
        self.assertEqual(parse_text("152: B, ok？"), {
            "result": "question", "id": 152, "choice": None,
            "words": "152: B, ok？",
        })

    def test_unicode_question_marks_are_questions_anywhere(self):
        """any supported Unicode question mark anywhere makes the reply a question"""
        for mark in ("\u037e", "\u061f", "\u2e2e", "\u203d", "\u2e18", "\U0001f679", "\U0001f67a", "\U0001f67b", "\u2048", "\u055e", "\u1367"):
            with self.subTest(mark=f"U+{ord(mark):04X}"):
                self.assertEqual(parse_text(f"152: B, ok{mark}"), {
                    "result": "question", "id": 152, "choice": None,
                    "words": f"152: B, ok{mark}",
                })

    def test_question_mark_anywhere_in_text_is_a_question(self):
        """question text remains a question after punctuation or invisible text"""
        for suffix in ("", "!", " thanks", "\u3164", "\u2800", "\u034f", "\ufe0f"):
            with self.subTest(suffix=repr(suffix)):
                text = f"152: B, ok?{suffix}"
                self.assertEqual(parse_text(text), {
                    "result": "question", "id": 152, "choice": None,
                    "words": "152: B, ok?" + (suffix if suffix in ("", "!", " thanks") else ""),
                })

    def test_trailing_zero_width_space_does_not_hide_question(self):
        """a trailing zero-width space does not hide a question"""
        self.assertEqual(parse_text("152: B?\u200b"), {
            "result": "question", "id": 152, "choice": None,
            "words": "152: B?",
        })

    def test_second_decision_in_reason_is_ambiguous(self):
        """a second decision in a reason is ambiguous"""
        self.assertEqual(parse_text("152: B. Also #153: A"), {
            "result": "ambiguous", "id": None, "choice": None,
            "words": "152: B. Also #153: A",
        })

    def test_second_decision_on_new_line_is_ambiguous(self):
        """a second decision on a new line is ambiguous"""
        self.assertEqual(parse_text("152: B\n153: A"), {
            "result": "ambiguous", "id": None, "choice": None,
            "words": "152: B\n153: A",
        })

    def test_second_hash_id_in_reason_is_ambiguous(self):
        """a second hash id in a reason is ambiguous"""
        text = "152: B, see #153"
        self.assertEqual(parse_text(text), {
            "result": "ambiguous", "id": None, "choice": None, "words": text,
        })

    def test_second_space_form_decision_is_ambiguous(self):
        """a second space-form decision is ambiguous"""
        text = "152: B and 153 C"
        self.assertEqual(parse_text(text), {
            "result": "ambiguous", "id": None, "choice": None, "words": text,
        })

    def test_second_lowercase_decision_is_ambiguous(self):
        """a second lowercase decision is ambiguous"""
        text = "152: b\n153: a"
        self.assertEqual(parse_text(text), {
            "result": "ambiguous", "id": None, "choice": None, "words": text,
        })

    def test_approve_n_picks_the_recommendation(self):
        """approve N picks the recommendation"""
        self.assertEqual(parse_text("approve 7"), {
            "result": "option", "id": 7, "choice": "rec", "words": "approve 7",
        })

    def test_free_text_naming_one_id_is_custom(self):
        """free text naming one id is custom"""
        self.assertEqual(parse_text("40 do the second one but later"), {
            "result": "custom", "id": 40, "choice": None,
            "words": "40 do the second one but later",
        })

    def test_a_hash_id_inside_text_is_custom(self):
        """a hash id inside text is custom"""
        self.assertEqual(parse_text("For #12 the banner can wait"), {
            "result": "custom", "id": 12, "choice": None,
            "words": "For #12 the banner can wait",
        })

    def test_a_question_is_a_question(self):
        """a question is a question"""
        self.assertEqual(parse_text("What does option B change?"), {
            "result": "question", "id": None, "choice": None,
            "words": "What does option B change?",
        })

    def test_a_question_with_an_id_keeps_the_id(self):
        """a question with an id keeps the id"""
        self.assertEqual(parse_text("#31 is this reversible?"), {
            "result": "question", "id": 31, "choice": None,
            "words": "#31 is this reversible?",
        })

    def test_text_with_no_id_is_ambiguous(self):
        """text with no id is ambiguous"""
        self.assertEqual(parse_text("Looks good to me"), {
            "result": "ambiguous", "id": None, "choice": None,
            "words": "Looks good to me",
        })

    def test_two_ids_are_ambiguous(self):
        """two ids are ambiguous"""
        self.assertEqual(parse_text("#3 and #4 both A"), {
            "result": "ambiguous", "id": None, "choice": None,
            "words": "#3 and #4 both A",
        })

    def test_empty_text_is_ambiguous(self):
        """empty text is ambiguous"""
        self.assertEqual(parse_text("   "), {
            "result": "ambiguous", "id": None, "choice": None, "words": "   ",
        })

    def test_a_letter_beyond_d_is_not_an_option(self):
        """a letter beyond D is not an option"""
        self.assertEqual(parse_text("5: E"), {
            "result": "custom", "id": 5, "choice": None, "words": "5: E",
        })

    def test_words_are_kept_exactly(self):
        """words are kept exactly"""
        self.assertEqual(parse_text("  126: a "), {
            "result": "option", "id": 126, "choice": "A", "words": "  126: a ",
        })


if __name__ == "__main__":
    unittest.main()

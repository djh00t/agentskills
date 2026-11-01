import unittest

from decide_parse import parse_text


class ParseTextTests(unittest.TestCase):
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
        for mark in ("\u037e", "\u061f", "\u2e2e", "\u203d", "\u2048", "\u055e", "\u1367"):
            with self.subTest(mark=f"U+{ord(mark):04X}"):
                self.assertEqual(parse_text(f"152: B, ok{mark}"), {
                    "result": "question", "id": 152, "choice": None,
                    "words": f"152: B, ok{mark}",
                })

    def test_question_mark_anywhere_in_text_is_a_question(self):
        """question text remains a question after punctuation or invisible text"""
        for suffix in ("", "!", " thanks", "\n\nthanks", "\u3164", "\u2800", "\u034f", "\ufe0f"):
            with self.subTest(suffix=repr(suffix)):
                text = f"152: B, ok?{suffix}"
                self.assertEqual(parse_text(text), {
                    "result": "question", "id": 152, "choice": None,
                    "words": text,
                })

    def test_trailing_zero_width_space_does_not_hide_question(self):
        """a trailing zero-width space does not hide a question"""
        self.assertEqual(parse_text("152: B?\u200b"), {
            "result": "question", "id": 152, "choice": None,
            "words": "152: B?\u200b",
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

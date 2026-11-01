import unittest
import time

from decide_lint import GENERIC_PATTERNS

from decide_lint import format_hits, iter_text_fields, join_wraps, lint_request, normalize, scan_text


class LintFeatureTests(unittest.TestCase):
    def test_github_token(self):
        """a GitHub token is found"""
        self.assertEqual(scan_text("gh" + "p_" + "A" * 36), ["github_token"])

    def test_openai_key(self):
        """an OpenAI-style key is found"""
        self.assertEqual(scan_text("sk-" + "A" * 24), ["openai_key"])

    def test_aws_key(self):
        """an AWS key id is found"""
        self.assertEqual(scan_text("AKIA" + "A" * 16), ["aws_key"])

    def test_private_key(self):
        """a private key header is found"""
        self.assertEqual(scan_text("-----BEGIN RSA PRIVATE KEY-----"), ["private_key"])

    def test_personal_email(self):
        """a personal email is found"""
        address = "person" + "@" + "example.com"
        self.assertEqual(scan_text(address), ["email"])

    def test_noreply_email(self):
        """a noreply GitHub email is allowed"""
        self.assertEqual(scan_text("bot@users.noreply.github.com"), [])

    def test_home_path(self):
        """a home path is found"""
        path = "/" + "Users/" + "zqxuser"
        self.assertEqual(scan_text(path), ["home_path"])

    def test_pushover_key(self):
        """a 30-character key near the word pushover is found"""
        self.assertEqual(scan_text("pushover " + "a" * 30), ["pushover_key"])

    def test_webhook_url(self):
        """a webhook URL is found"""
        self.assertEqual(scan_text("https://example.com/webhook/abc"), ["webhook_url"])

    def test_nine_digit_number(self):
        """a nine-digit number is found"""
        number = "123" + "456" + "789"
        self.assertEqual(scan_text(number), ["long_number"])

    def test_commit_sha_not_number(self):
        """a 40-hex commit sha is not a long number"""
        self.assertEqual(scan_text("a" + "0123456789" * 3 + "abcdefabc"), [])

    def test_request_path(self):
        """lint_request names the field path"""
        token = "gh" + "p_" + "A" * 36
        address = "person" + "@" + "example.com"
        req = {"key": token, "options": [{"text": "safe"}, {"changes": "call " + address}]}
        self.assertEqual(
            lint_request(req),
            [("key", "github_token"), ("options[1].changes", "email")],
        )

    def test_report_hides_value(self):
        """the hit report never contains the matched text"""
        value = "gh" + "p_" + "A" * 36
        hits = lint_request({"key": value})
        report = format_hits(hits)
        self.assertEqual(report, "key: matches github_token")
        for output in (str(hits), repr(hits), report):
            self.assertNotIn(value[:8], output)
            self.assertNotIn(value[8:], output)
        key_hits = lint_request({value: "safe"})
        self.assertNotIn(value[:8], format_hits(key_hits))
        self.assertNotIn(value[8:], repr(key_hits))

    def test_normalized_secrets(self):
        """normalized and wrapped secrets are found"""
        token = "gh" + "p_" + "A" * 36
        for value in ("ｇｈｐ＿" + "Ａ" * 36, token[:8] + "\u200b" + token[8:],
                      token[:8] + "\n" + token[8:], token.upper(), "akia" + "a" * 16):
            self.assertTrue(scan_text(value))

    def test_pgp_and_email_suffix(self):
        """private key blocks and noreply suffixes are found"""
        self.assertIn("private_key", scan_text("-----begin pgp private key block-----"))
        for suffix in (".invalid", "-mail.invalid"):
            self.assertIn("email", scan_text("x@users.noreply.github.com" + suffix))

    def test_nested_unknown_fields(self):
        """unknown nested text fields are scanned"""
        token = "gh" + "p_" + "A" * 36
        self.assertEqual(lint_request({"new": [{"nested": token}]}),
                         [("new[0].nested", "github_token")])

    def test_patterns_are_fast(self):
        """long nonmatching fields are scanned quickly"""
        patterns = dict(GENERIC_PATTERNS)
        for name, value in (("email", "a." * 80000), ("webhook_url", "http://" * 22857 + "x")):
            start = time.monotonic()
            patterns[name].search(value)
            self.assertLess(time.monotonic() - start, 0.5, name)
            start = time.monotonic()
            with self.assertRaises(Exception):
                scan_text(value)
            self.assertLess(time.monotonic() - start, 0.5, name + " scan")

    def test_pr_numbers_are_not_text(self):
        """ids and numbers in a PR field are not text"""
        number = int("123" + "456" + "789")
        self.assertEqual(lint_request({"pr": {"number": number}}), [])

    def test_sentence_email(self):
        """a sentence-ending address is found"""
        address = "person" + "@" + "example.com"
        self.assertIn("email", scan_text(address + ". Thanks"))
        self.assertEqual(scan_text("bot@users.noreply.github.com. ok"), [])

    def test_invisible_characters(self):
        """invisible characters do not hide secrets"""
        token = "gh" + "p_" + "A" * 36
        for invisible in ("\ufe0f", "\U000e0100", "\u034f", "\u20dd", "\u115f", "\u1160",
                          "\u3164", "\uffa0", "\u2800", "\U000e0000", "\u200b\u0301"):
            with self.subTest(invisible=ascii(invisible)):
                self.assertIn("github_token", scan_text(token[:8] + invisible + token[8:]))

    def test_combining_marks_controls_and_surrogates(self):
        """combining marks controls and surrogates do not hide secrets"""
        token = "gh" + "p_" + "A" * 36
        characters = [chr(code) for code in range(0x300, 0x370)]
        characters += [chr(code) for code in range(0x20) if code not in (9, 10, 13)]
        characters += [chr(code) for code in range(0x7f, 0xa0) if code != 0x85]
        characters += ["\ud800"]
        for char in characters:
            with self.subTest(char=ascii(char)):
                self.assertIn("github_token", scan_text(token[:8] + char + token[8:]))
        self.assertIn("email", scan_text("x@exa\u0308mple.com"))
        self.assertNotIn("github_token", scan_text(token[:8] + "\t" + token[8:]))

    def test_recomposition_preserves_pushover_window(self):
        """recomposition preserves the pushover detection window"""
        text = "pushover " + "\u1100\u200b\u1161" * 20 + " " + "a" * 30
        self.assertIn("pushover_key", scan_text(text))

    def test_depth_and_scalar_boundaries(self):
        """depth and scalar boundaries are enforced"""
        for container in (lambda value: [value], lambda value: {"a": value}):
            value = "safe"
            for _ in range(256):
                value = container(value)
            self.assertEqual(lint_request(value), [])
            with self.assertRaises(ValueError):
                lint_request(container(value))
        self.assertEqual(lint_request({"a": None, "b": 1.5, "c": True, "d": 2}), [])

    def test_key_and_pattern_boundaries(self):
        """key labels and pattern boundaries are enforced"""
        token = "gh" + "p_" + "A" * 36
        self.assertEqual(lint_request({"a" * 64: token, "a.b": token}),
                         [("a" * 64, "github_token"), ("[key1]", "github_token")])
        self.assertEqual(lint_request([token, "sk-" + "A" * 24]),
                         [("[0]", "github_token"), ("[1]", "openai_key")])
        self.assertIn("pushover_key", scan_text("pushover" + " " * 40 + "a" * 30))
        self.assertNotIn("pushover_key", scan_text("pushover" + " " * 41 + "a" * 30))
        self.assertNotIn("long_number", scan_text("12345678"))

    def test_untrusted_keys(self):
        """untrusted keys are scanned and safely labelled"""
        token = "gh" + "p_" + "A" * 36
        self.assertEqual(lint_request({token: "safe"}), [("[key0]", "github_token")])
        self.assertEqual(lint_request({"unsafe key": token}), [("[key0]", "github_token")])
        self.assertEqual(lint_request({"a" * 65: token}), [("[key0]", "github_token")])

    def test_rejects_unknown_types_and_deep_nesting(self):
        """unsupported values and excessive nesting are rejected"""
        self.assertEqual(lint_request({"value": None}), [])
        for value in ((), set(), b"data", object()):
            with self.subTest(value=type(value)):
                with self.assertRaises(TypeError):
                    lint_request({"value": value})
        with self.assertRaisesRegex(TypeError, "request keys must be strings"):
            lint_request({1: "safe"})
        value = []
        for _ in range(1200):
            value = [value]
        with self.assertRaises(ValueError):
            lint_request(value)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(ValueError):
            lint_request(cycle)

    def test_join_wraps_long_spaces_is_fast(self):
        start = time.monotonic()
        self.assertEqual(join_wraps(" " * 32000), " " * 32000)
        self.assertLess(time.monotonic() - start, 0.5)

    def test_scan_limit_exact_boundary(self):
        self.assertEqual(len(normalize("a" * 65536)), 65536)
        self.assertEqual(len(normalize("a" * 65535 + "é")), 65536)

    def test_wrap_trimming_preserves_nonwrap_whitespace(self):
        self.assertEqual(join_wraps(" a  \n  b "), " ab ")
        self.assertEqual(join_wraps("a  \\\n  b"), "ab")
        self.assertEqual(join_wraps("a\n\n b"), "ab")
        self.assertEqual(join_wraps("a\\\nb"), "ab")
        self.assertEqual(join_wraps("\n\\"), "\\")

    def test_sensitive_key_obeys_depth_limit(self):
        token = "gh" + "p_" + "A" * 36
        value = {token: "safe"}
        for _ in range(255):
            value = {"a": value}
        self.assertEqual(len(lint_request(value)), 1)
        with self.assertRaisesRegex(ValueError, "request nesting exceeds limit"):
            next(iter_text_fields({"a": value}))

    def test_line_wraps(self):
        """line wraps do not hide secrets"""
        token = "gh" + "p_" + "A" * 36
        for wrap in ("\n  ", "  \n", "\r", "\u2028", "\u2029", "\x85", "\\\n"):
            with self.subTest(wrap=ascii(wrap)):
                self.assertIn("github_token", scan_text(token[:8] + wrap + token[8:]))


if __name__ == "__main__":
    unittest.main()

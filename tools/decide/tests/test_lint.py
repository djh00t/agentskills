import unittest
import time

from decide_lint import GENERIC_PATTERNS

from decide_lint import format_hits, lint_request, scan_text


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

    def test_pr_numbers_are_not_text(self):
        """ids and numbers in a PR field are not text"""
        number = int("123" + "456" + "789")
        self.assertEqual(lint_request({"pr": {"number": number}}), [])


if __name__ == "__main__":
    unittest.main()

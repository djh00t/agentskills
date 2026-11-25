"""Offline acceptance tests: security and HTTP are always mocked."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import cg_wake

KEY = "SENTINEL-SECRET-KEY"
URL = "https://SENTINEL-URL/wake"


class WakeTests(unittest.TestCase):
    def run_wake(self, values=(KEY, URL), status=204, error=None):
        result = {"success": True, "text": "private message text"}
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(output), \
                patch("cg_wake.subprocess.run") as security, \
                patch("cg_wake.http.client.HTTPSConnection") as http:
            security.side_effect = [
                value if isinstance(value, Exception) else
                CompletedProcess([], 0 if value else 1, value)
                for value in values
            ]
            http.return_value.getresponse.return_value.status = status
            http.return_value.request.side_effect = error
            returned = cg_wake.wake_after_send("conversation", 7, result)
            self.assertIs(returned, result)
            self.assertEqual(result, {"success": True, "text": "private message text"})
            self.assertEqual(list(Path(directory).rglob("*")), [])
        for secret in (KEY, URL):
            self.assertNotIn(secret, output.getvalue())
        self.assertEqual(security.call_count, 2)
        for call, account in zip(security.call_args_list, ("webhook-key", "webhook-url")):
            self.assertEqual(call.args, (["security", "find-generic-password", "-s",
                                         "codex-grok-wake", "-a", account, "-w"],))
            self.assertNotIn(KEY, repr(call))
            self.assertNotIn(URL, repr(call))
        return output.getvalue(), http

    def test_missing_items_disable_once(self):
        for values in (("", URL), (KEY, ""), ("", ""),
                       (FileNotFoundError(), FileNotFoundError())):
            with self.subTest(values=tuple(bool(value) for value in values)):
                output, http = self.run_wake(values)
                self.assertEqual(output, "wake disabled: keychain item absent\n")
                http.assert_not_called()

    def test_success_posts_only_routing_fields(self):
        output, http = self.run_wake()
        self.assertEqual(output, "ping ok\n")
        http.assert_called_once_with("sentinel-url", None, timeout=5)
        request = http.return_value.request
        request.assert_called_once()
        self.assertEqual(request.call_args.args, ("POST", "/wake"))
        self.assertEqual(json.loads(request.call_args.kwargs["body"]),
                         {"conversation_id": "conversation", "seq": 7})
        self.assertEqual(request.call_args.kwargs["headers"],
                         {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        http.return_value.close.assert_called_once()

    def test_http_failures_do_not_change_send(self):
        for status in (302, 401, 500):
            with self.subTest(status=status):
                output, http = self.run_wake(status=status)
                self.assertEqual(output, f"ping failed ({status})\n")
                http.return_value.request.assert_called_once()

    def test_exception_details_never_escape(self):
        for error in (TimeoutError(KEY + URL), OSError(KEY + URL), ValueError(KEY + URL)):
            output, http = self.run_wake(error=error)
            self.assertEqual(output, "ping failed (timeout)\n")
            http.return_value.request.assert_called_once()

    def test_cli(self):
        with patch("sys.argv", ["cg_wake.py", "--conversation-id", "conversation", "--seq", "7"]), \
                patch("cg_wake.wake_after_send") as wake:
            cg_wake.main()
        wake.assert_called_once_with("conversation", 7, None)

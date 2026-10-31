import io
import json
import os
import stat
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import codex_turn_events as cte

KEY_SECRET, PATH_SECRET = "key-secret-abc", "/hook/secret-path-xyz"


def capture_server(status=204, location=None):
    """Local HTTP server recording each request; optionally answers with a redirect."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers["Content-Length"] or 0))
            seen.append({"auth": self.headers.get("Authorization"), "body": json.loads(body or b"{}")})
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen, f"http://127.0.0.1:{server.server_port}{PATH_SECRET}"


class CodexTurnEventsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.server, self.seen, self.url = capture_server()
        self.servers = [self.server]
        self.env = mock.patch.dict(os.environ, {"CODEX_TURN_EVENTS_DIR": str(self.state),
                                                "CODEX_EVENTS_WEBHOOK_URL": self.url,
                                                "CODEX_EVENTS_WEBHOOK_KEY": KEY_SECRET})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        for s in self.servers:
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def hook(self, event, payload):
        out = io.StringIO()
        text = payload if isinstance(payload, str) else json.dumps(payload)
        with redirect_stdout(out), mock.patch("sys.stdin", io.StringIO(text)):
            cte.main(["hook", event])
        return out.getvalue()

    def rows(self, name):
        path = self.state / name
        return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

    def assert_private_on_disk(self):
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        for f in self.state.iterdir():
            self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600, f.name)
            self.assertNotIn("secret-path-xyz", f.read_text())
            self.assertNotIn(KEY_SECRET, f.read_text())

    def test_stop_posts_minimal_turn_complete_with_stable_event_id(self):
        payload = {"session_id": "s1", "turn_id": "t1", "cwd": "/home/me/agentskills", "model": "gpt-6.1-sol",
                   "stop_hook_active": False,
                   "last_assistant_message": "Secret-ish text. Opened https://github.com/o/r/pull/26."}
        self.assertEqual(self.hook("stop", payload).strip(), "{}")
        self.assertEqual(self.hook("stop", payload | {"stop_hook_active": True}).strip(), "{}")
        first, second = (s["body"] for s in self.seen)
        self.assertEqual(self.seen[0]["auth"], f"Bearer {KEY_SECRET}")
        self.assertEqual(set(first), {"source", "event", "event_id", "session_id", "turn_id", "task", "model",
                                      "status", "pr_url", "stop_hook_active", "ts"})
        self.assertEqual((first["event_id"], first["task"], first["pr_url"], first["stop_hook_active"]),
                         ("codex:s1:t1:turn_complete", "agentskills", "https://github.com/o/r/pull/26", False))
        self.assertEqual((second["event_id"], second["stop_hook_active"]), (first["event_id"], True))
        self.assertNotIn("Secret-ish", json.dumps(first))
        self.assertTrue(all(r["posted"] for r in self.rows("delivery.jsonl")))
        self.assert_private_on_disk()

    def test_permission_request_posts_needs_approval_without_description(self):
        payload = {"session_id": "s1", "turn_id": "t1", "cwd": "/home/me/agentskills", "tool_name": "Bash",
                   "tool_input": {"command": "git push", "description": "push secret branch"}}
        self.hook("permission_request", payload)
        self.hook("permission_request", payload)
        a, b = (s["body"] for s in self.seen)
        self.assertEqual((a["event"], a["status"], a["tool_name"]), ("needs_approval", "waiting_for_human", "Bash"))
        self.assertTrue(a["event_id"].startswith("codex:s1:t1:needs_approval:"))
        self.assertEqual(a["event_id"], b["event_id"])
        self.assertTrue(a["wait_started_at"])
        for leak in ("description", "cwd", "summary", "git push", "/home/me"):
            self.assertNotIn(leak, json.dumps(a))
        self.assert_private_on_disk()

    def test_redirect_is_refused_and_key_never_follows(self):
        other, other_seen, other_url = capture_server()
        redirector, _, redirect_url = capture_server(status=302, location=other_url)
        self.servers += [other, redirector]
        with mock.patch.dict(os.environ, {"CODEX_EVENTS_WEBHOOK_URL": redirect_url}):
            self.assertEqual(self.hook("stop", {"session_id": "s1", "turn_id": "t1"}).strip(), "{}")
        self.assertEqual(other_seen, [])
        row = self.rows("delivery.jsonl")[0]
        self.assertEqual((row["posted"], row["post_status"]), (False, 302))
        self.assert_private_on_disk()

    def test_url_must_be_https_or_local_http(self):
        self.assertTrue(cte.url_allowed("https://hooks.example.com/x"))
        self.assertTrue(cte.url_allowed("http://localhost:8080/x"))
        self.assertFalse(cte.url_allowed("http://hooks.example.com/x"))
        self.assertFalse(cte.url_allowed("ftp://127.0.0.1/x"))
        with mock.patch.dict(os.environ, {"CODEX_EVENTS_WEBHOOK_URL": "http://hooks.example.com/secret-path-xyz"}):
            self.hook("stop", {"session_id": "s1", "turn_id": "t1"})
        self.assertEqual(self.rows("delivery.jsonl")[0]["post_error"], "invalid_url")
        self.assert_private_on_disk()

    def test_hook_never_fails_the_turn(self):
        with mock.patch.dict(os.environ, {"CODEX_EVENTS_WEBHOOK_URL": "http://127.0.0.1:9/x"}):
            self.assertEqual(self.hook("stop", {"session_id": "s1", "turn_id": "t9"}).strip(), "{}")
        self.assertFalse(self.rows("delivery.jsonl")[0]["posted"])
        self.assertEqual(self.hook("stop", "not json").strip(), "{}")
        self.assertEqual(self.rows("hook-errors.jsonl")[0]["error"], "JSONDecodeError")
        self.assert_private_on_disk()


if __name__ == "__main__":
    unittest.main()

import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import codex_turn_events as cte

URL_SECRET, KEY_SECRET = "http://127.0.0.1:{port}/hook/secret-path-xyz", "key-secret-abc"


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def usage(i, c, o):
    return {"input_tokens": i, "cached_input_tokens": c, "cache_write_input_tokens": 0,
            "output_tokens": o, "reasoning_output_tokens": 0}


def rollout(session, turn, started, complete=True):
    rows = [
        {"type": "session_meta", "payload": {"session_id": session, "cwd": "/w/agentskills"}},
        {"type": "turn_context", "payload": {"turn_id": turn, "model": "gpt-6.1-sol", "cwd": "/w/agentskills"}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": turn, "started_at": started}},
        {"type": "token_usage_record", "payload": {"turn_id": turn, "response_id": "r1", "usage": usage(100, 40, 10)}},
        {"type": "token_usage_record", "payload": {"turn_id": turn, "response_id": "r2", "usage": "broken"}},
    ]
    if complete:
        rows.append({"type": "event_msg", "payload": {"type": "task_complete", "turn_id": turn,
                                                      "started_at": started, "duration_ms": 4200}})
    return rows


class Capture(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Capture.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": json.loads(body)})
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


class CodexTurnEventsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state, self.sessions = root / "state", root / "sessions"
        self.server = HTTPServer(("127.0.0.1", 0), Capture)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        Capture.seen = []
        self.url = URL_SECRET.format(port=self.server.server_port)
        self.env = mock.patch.dict(os.environ, {
            "CODEX_TURN_EVENTS_DIR": str(self.state), "CODEX_SESSIONS_DIR": str(self.sessions),
            "CODEX_EVENTS_WEBHOOK_URL": self.url, "CODEX_EVENTS_WEBHOOK_KEY": KEY_SECRET})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def hook(self, event, payload):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("sys.stdin", io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))):
            cte.main(["hook", event])
        return out.getvalue()

    def rows(self, name):
        return list(cte.read_jsonl(self.state / name))

    def assert_no_secrets_on_disk(self):
        for f in self.state.rglob("*"):
            text = f.read_text()
            self.assertNotIn("secret-path-xyz", text)
            self.assertNotIn(KEY_SECRET, text)

    def test_stop_logs_turn_and_posts_event(self):
        path = self.sessions / "2026/10/31/rollout-a.jsonl"
        write_jsonl(path, rollout("s1", "t1", 1793408935))
        out = self.hook("stop", {"session_id": "s1", "turn_id": "t1", "cwd": "/w/agentskills", "model": "gpt-6.1-sol",
                                 "transcript_path": str(path),
                                 "last_assistant_message": "Opened https://github.com/djh00t/agentskills/pull/26 for review."})
        self.assertEqual(out.strip(), "{}")
        turn = self.rows("turns.jsonl")[0]
        self.assertEqual((turn["model"], turn["calls"], turn["input_tokens"], turn["cache_read_tokens"]), ("gpt-6.1-sol", 1, 100, 40))
        self.assertEqual((turn["wall_clock_s"], turn["wall_clock_exact"]), (4.2, True))
        sent = Capture.seen[0]
        self.assertEqual(sent["auth"], f"Bearer {KEY_SECRET}")
        self.assertEqual({k: sent["body"][k] for k in ("event", "session_id", "task", "status", "pr_url")},
                         {"event": "turn_complete", "session_id": "s1", "task": "agentskills", "status": "completed",
                          "pr_url": "https://github.com/djh00t/agentskills/pull/26"})
        self.assertTrue(self.rows("events.jsonl")[0]["posted"])
        self.assert_no_secrets_on_disk()

    def test_permission_request_posts_needs_approval_and_starts_wait_clock(self):
        out = self.hook("permission_request", {"session_id": "s1", "turn_id": "t1", "cwd": "/w/agentskills",
                                               "tool_name": "shell", "tool_input": {"description": "git push"}})
        self.assertEqual(out.strip(), "{}")
        body = Capture.seen[0]["body"]
        self.assertEqual((body["event"], body["status"], body["tool_name"], body["description"]),
                         ("needs_approval", "waiting_for_human", "shell", "git push"))
        self.assertTrue(self.rows("events.jsonl")[0]["wait_started_at"])
        self.assert_no_secrets_on_disk()

    def test_hook_never_fails_the_turn(self):
        with mock.patch.dict(os.environ, {"CODEX_EVENTS_WEBHOOK_URL": "http://127.0.0.1:9/x"}):
            self.assertEqual(self.hook("stop", {"session_id": "s1", "turn_id": "t9"}).strip(), "{}")
        self.assertFalse(self.rows("events.jsonl")[0]["posted"])
        self.assertEqual(self.hook("stop", "not json").strip(), "{}")
        self.assertEqual(self.rows("hook-errors.jsonl")[0]["error"], "JSONDecodeError")
        self.assert_no_secrets_on_disk()

    def test_reconcile_fills_missed_turns_once_and_reports_gaps(self):
        write_jsonl(self.sessions / "2026/10/30/rollout-old.jsonl", rollout("s0", "t0", 1793300000))
        write_jsonl(self.sessions / "2026/10/31/rollout-a.jsonl", rollout("s1", "t1", 1793408935))
        write_jsonl(self.sessions / "2026/10/31/rollout-b.jsonl", rollout("s2", "t2", 1793409000, complete=False))
        cte.append_jsonl("turns.jsonl", {"session_id": "s1", "turn_id": "t1", "wall_clock_exact": False})
        with redirect_stdout(io.StringIO()):
            first = cte.reconcile(cte.date(2026, 10, 31))
        self.assertEqual((first["turns"], first["filled_missing"], first["upgraded_wall_clock"]), (2, 1, 1))
        self.assertEqual(first["missing_by_day"], {"2026-10-31": 1})
        t2 = [r for r in self.rows("turns.jsonl") if r["turn_id"] == "t2"][0]
        self.assertIsNone(t2["wall_clock_s"])
        second = cte.reconcile(cte.date(2026, 10, 31))
        self.assertEqual((second["filled_missing"], second["upgraded_wall_clock"]), (0, 0))
        self.assertTrue((self.state / "reconcile-state.json").exists())


if __name__ == "__main__":
    unittest.main()

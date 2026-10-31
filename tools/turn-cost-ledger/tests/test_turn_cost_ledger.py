import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import turn_cost_ledger as tcl

# The real fsm-ledger writer, so a schema mismatch fails here, not in production.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "feature-status-matrix"))
from fsm_ledger.ledger import append_dict  # noqa: E402


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((json.dumps(r) if not isinstance(r, str) else r) + "\n" for r in rows), encoding="utf-8")


def usage(i, c, o, r=0):
    return {"input_tokens": i, "cached_input_tokens": c, "cache_write_input_tokens": 0,
            "output_tokens": o, "reasoning_output_tokens": r}


class TurnCostLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.sessions, self.ledger = root / "sessions", root / "ledger"
        write_jsonl(self.sessions / "2026/10/31/rollout-a.jsonl", [
            {"type": "session_meta", "payload": {"session_id": "s1", "cwd": "/w"}},
            {"type": "turn_context", "timestamp": "2026-10-31T01:00:00Z",
             "payload": {"turn_id": "t1", "model": "deepseek-v4-flash"}},
            {"type": "token_usage_record", "payload": {"turn_id": "t1", "response_id": "r1", "usage": usage(100, 60, 10, 2)}},
            {"type": "token_usage_record", "payload": {"turn_id": "t1", "response_id": "r2", "usage": usage(200, 150, 20)}},
            {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "t1",
                                              "duration_ms": 12500, "time_to_first_token_ms": 900}},
            "not-a-dict",
        ])
        write_jsonl(self.sessions / "2026/10/30/rollout-b.jsonl", [
            {"type": "session_meta", "payload": {"session_id": "s2"}},
            {"type": "turn_context", "timestamp": "2026-10-30T02:00:00Z",
             "payload": {"turn_id": "t2", "model": "gpt-6.1-sol"}},
            {"type": "token_usage_record", "payload": {"turn_id": "t2", "response_id": "r3",
                                                       "usage": {"input_tokens": "n/a", "output_tokens": 5}}},
            {"type": "token_usage_record", "payload": {"turn_id": "t2", "response_id": "r4", "usage": "broken"}},
        ])
        write_jsonl(self.sessions / "2026/10/29/rollout-c.jsonl", [
            {"type": "session_meta", "payload": {"session_id": "s3"}},
            {"type": "turn_context", "payload": {"turn_id": "t3", "model": "gpt-6.1-sol"}},
            {"type": "token_usage_record", "payload": {"turn_id": "t3", "response_id": "r5", "usage": usage(50, 0, 5)}},
            {"type": "turn_context", "payload": {"turn_id": "t4", "model": "gpt-6.1-sol"}},
            {"type": "token_usage_record", "payload": {"turn_id": "t4", "response_id": "r6", "usage": usage(50, 0, 5)}},
        ])
        self.append({"event_id": "codex:s1:r1", "session_id": "s1", "model": "deepseek-v4-flash",
                     "inputTokens": 100, "outputTokens": 10, "costTotal": 0.001})
        for rid in ("r5", "r6"):
            self.append({"event_id": f"codex:s3:{rid}", "session_id": "s3", "model": "gpt-6.1-sol",
                         "inputTokens": 50, "outputTokens": 5, "billing_mode": "subscription"})
        # The committed writer drops api_equivalent_usd; the live fsm-ledger billing
        # code adds it to subscription rows, so add it to r5's stored row the same way.
        usage_file = next(self.ledger.glob("*/usage.jsonl"))
        rows = [json.loads(x) for x in usage_file.read_text(encoding="utf-8").splitlines()]
        for row in rows:
            if row["event_id"] == "codex:s3:r5":
                row["api_equivalent_usd"] = 0.002
        write_jsonl(usage_file, rows)

    def append(self, raw):
        with mock.patch.dict(os.environ, {"FSM_MATRICES_ROOT": str(self.ledger), "FSM_PROJECT": "proj"}):
            result = append_dict(raw | {"harness": "codex", "cwd": "/w"})
        self.assertTrue(result.get("ok"), result)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            tcl.main(["--sessions", str(self.sessions), "--ledger-root", str(self.ledger), "--format", "jsonl", *extra])
        return {r["turn_id"]: r for r in map(json.loads, buf.getvalue().splitlines())}

    def test_turn_sums_calls_and_records_wall_clock(self):
        row = self.run_cli()["t1"]
        self.assertEqual((row["model"], row["calls"]), ("deepseek-v4-flash", 2))
        self.assertEqual((row["input_tokens"], row["cache_read_tokens"], row["output_tokens"]), (300, 210, 30))
        self.assertEqual((row["wall_clock_s"], row["ttft_s"]), (12.5, 0.9))

    def test_unpriced_call_marks_cost_incomplete(self):
        row = self.run_cli()["t1"]
        self.assertEqual(row["est_cost_usd"], 0.001)
        self.assertEqual(row["calls_unpriced"], 1)
        self.assertFalse(row["cost_complete"])

    def test_malformed_usage_is_skipped_not_fatal(self):
        row = self.run_cli()["t2"]
        self.assertEqual((row["calls"], row["input_tokens"], row["output_tokens"]), (1, 0, 5))

    def test_subscription_row_uses_api_equivalent_usd(self):
        row = self.run_cli()["t3"]
        self.assertEqual((row["est_cost_usd"], row["calls_unpriced"], row["cost_complete"]), (0.002, 0, True))

    def test_subscription_row_without_api_equivalent_is_unpriced_not_zero(self):
        row = self.run_cli()["t4"]
        self.assertEqual((row["est_cost_usd"], row["calls_unpriced"], row["cost_complete"]), (0.0, 1, False))

    def test_since_takes_iso_date_and_filters_by_path_date(self):
        self.assertEqual(set(self.run_cli("--since", "2026-10-31")), {"t1"})
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_cli("--since", "2026/10/31")


if __name__ == "__main__":
    unittest.main()

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import turn_cost_ledger as tcl


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


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
        write_jsonl(self.ledger / "_unattributed/usage.jsonl", [
            {"response_id": "r1", "costTotal": 0.001, "pricing_date": "2026-10-30",
             "source_url": "https://models.dev/models/deepseek/deepseek-v4-flash/"},
        ])
        write_jsonl(self.sessions / "2026/10/31/rollout-b.jsonl", [
            {"type": "session_meta", "payload": {"session_id": "s2"}},
            {"type": "turn_context", "timestamp": "2026-10-31T02:00:00Z",
             "payload": {"turn_id": "t2", "model": "gpt-6.1-sol"}},
            {"type": "token_usage_record", "payload": {"turn_id": "t2", "response_id": "r3", "usage": usage(10, 0, 1)}},
        ])
        write_jsonl(self.ledger / "proj/usage.jsonl", [
            {"response_id": "r3", "costTotal": 0.0, "cost_is_plan": True, "api_equivalent_usd": 0.5},
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            tcl.main(["--sessions", str(self.sessions), "--ledger-root", str(self.ledger), "--format", "jsonl"])
        return [json.loads(line) for line in buf.getvalue().splitlines()]

    def test_turn_sums_calls_and_records_wall_clock(self):
        row = self.run_cli()[0]
        self.assertEqual((row["model"], row["calls"]), ("deepseek-v4-flash", 2))
        self.assertEqual((row["input_tokens"], row["cache_read_tokens"], row["output_tokens"]), (300, 210, 30))
        self.assertEqual((row["wall_clock_s"], row["ttft_s"]), (12.5, 0.9))

    def test_unpriced_call_marks_cost_incomplete(self):
        row = self.run_cli()[0]
        self.assertEqual(row["est_cost_usd"], 0.001)
        self.assertEqual(row["calls_unpriced"], 1)
        self.assertFalse(row["cost_complete"])
        self.assertEqual(row["pricing_date"], "2026-10-30")

    def test_subscription_call_uses_api_equivalent_not_plan(self):
        row = self.run_cli()[1]
        self.assertEqual((row["est_cost_usd"], row["cost_complete"]), (0.5, True))


if __name__ == "__main__":
    unittest.main()

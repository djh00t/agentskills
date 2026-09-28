"""Unit tests for fsm_ledger (append, attribute, pricer) + compact render."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Skill root on path
SKILL = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(SKILL))
sys.path.insert(0, str(SKILL / "tools"))

from fsm_ledger.attribute import (
    bind_active_wp,
    resolve_project,
    resolve_work_package,
    UNKNOWN_PROJECT,
    _wp_from_branch_or_subject,
)
from fsm_ledger.ledger import append_dict
from fsm_ledger.pricer import estimate_cost, price_event
from fsm_ledger.schema import UNALLOCATED, normalize_event
from render_matrix import aggregate_usage, load_packages_json, render_markdown


class SchemaTest(unittest.TestCase):
    def test_normalize_and_unallocated_default(self):
        ev = normalize_event({"inputTokens": 10, "outputTokens": 5, "model": "gpt-6-luna"})
        self.assertEqual(ev.workPackageId, UNALLOCATED)
        self.assertEqual(ev.totalTokens, 15)
        self.assertTrue(ev.event_id)

    def test_cache_write_count_preserves_zero_and_unknown(self):
        self.assertEqual(normalize_event({"cacheWriteInputTokens": 0}).to_dict()["cacheWriteInputTokens"], 0)
        self.assertNotIn("cacheWriteInputTokens", normalize_event({}).to_dict())
        self.assertNotIn("cachedInputTokens", normalize_event({}).to_dict())


class AttributeTest(unittest.TestCase):
    def test_branch_heuristic_ab_id(self):
        self.assertEqual(_wp_from_branch_or_subject("feat/AB-033-videos"), "AB-033")
        self.assertEqual(_wp_from_branch_or_subject("AB-034 whisper"), "AB-034")

    def test_branch_heuristic_feat_enrich(self):
        self.assertEqual(_wp_from_branch_or_subject("feat(enrich)"), "AB-033")
        self.assertEqual(_wp_from_branch_or_subject("feat/enrich-s3"), "AB-033")

    def test_env_wp_wins(self):
        with mock.patch.dict(os.environ, {"FSM_WP": "AB-051"}, clear=False):
            wp = resolve_work_package(cwd="/tmp", project="agent-brain")
            self.assertEqual(wp, "AB-051")

    def test_active_wp_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proj = root / "agent-brain"
            proj.mkdir()
            (proj / "active-wp.json").write_text(json.dumps({"workPackageId": "AB-033"}), encoding="utf-8")
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("FSM_WP", None)
                    os.environ.pop("FEATURE_WP", None)
                    wp = resolve_work_package(cwd="/path/that/is/not/available", project="agent-brain")
                    self.assertEqual(wp, "AB-033")

    def test_configured_root_resolves_agent_brain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": ["/Users/djh/work/src/github.com_local/djh00t/agent-brain"]}),
                encoding="utf-8",
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("FSM_PROJECT", None)
                    os.environ.pop("FEATURE_PROJECT", None)
                    p = resolve_project(cwd="/Users/djh/work/src/github.com_local/djh00t/agent-brain")
                    self.assertEqual(p, "agent-brain")

    def test_cwd_conflict_rejects_explicit_project_hint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for project, cwd in (("agent-brain", root / "agent-brain"), ("openai-finance", root / "openai-finance")):
                cwd.mkdir()
                (root / project / "project.json").write_text(
                    json.dumps({"id": project, "roots": [str(cwd)]}), encoding="utf-8"
                )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                self.assertEqual(
                    resolve_project(cwd=str(root / "openai-finance"), hint="agent-brain"),
                    UNKNOWN_PROJECT,
                )

    def test_matching_cwd_keeps_explicit_project_hint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cwd = root / "agent-brain"
            cwd.mkdir()
            (cwd.parent / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": [str(cwd)]}), encoding="utf-8"
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                self.assertEqual(resolve_project(cwd=str(cwd), hint="agent-brain"), "agent-brain")

    def test_valid_hint_is_preserved_when_cwd_has_no_project(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": []}), encoding="utf-8"
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                self.assertEqual(resolve_project(cwd=str(root / "unknown"), hint="agent-brain"), "agent-brain")

    def test_existing_unknown_cwd_rejects_project_hint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            foreign = root / "openai_finance"
            foreign.mkdir()
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": []}), encoding="utf-8"
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                self.assertEqual(resolve_project(cwd=str(foreign), hint="agent-brain"), UNKNOWN_PROJECT)

    def test_unrelated_cwd_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": []}), encoding="utf-8"
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                self.assertEqual(resolve_project(cwd="/Users/djh/work/src/github.com_local/djh00t/openai_finance"), UNKNOWN_PROJECT)

    def test_malicious_and_empty_hints_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": []}), encoding="utf-8"
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                self.assertEqual(resolve_project(cwd="/tmp", hint="../escape"), UNKNOWN_PROJECT)
                self.assertEqual(resolve_project(cwd="/tmp", hint="/tmp/escape"), UNKNOWN_PROJECT)
                self.assertEqual(resolve_project(cwd="/tmp", hint="   "), UNKNOWN_PROJECT)

    def test_invalid_env_project_fails_closed_and_valid_env_is_preserved(self):
        with mock.patch.dict(os.environ, {"FSM_PROJECT": "../escape"}, clear=False):
            self.assertEqual(resolve_project(cwd="/tmp"), UNKNOWN_PROJECT)
        with mock.patch.dict(os.environ, {"FSM_PROJECT": " agent-brain "}, clear=False):
                self.assertEqual(resolve_project(cwd="/path/that/is/not/available"), "agent-brain")


class PricerTest(unittest.TestCase):
    def test_estimate_from_pricing_table(self):
        # Uses real table path if present; skip if missing
        try:
            est = estimate_cost(1_000_000, 1_000_000, "gpt-6-luna")
        except FileNotFoundError:
            self.skipTest("pricing table not found")
        self.assertAlmostEqual(est["usd_total"], 0.10 + 0.50, places=4)

    def test_subscription_zeros_cost(self):
        row = price_event({"billing_mode": "subscription", "costTotal": 9.99, "model": "gpt-6-luna"})
        self.assertEqual(row["costTotal"], 0.0)
        self.assertTrue(row["cost_is_plan"])

    def test_provider_reported_cost_preferred(self):
        row = price_event(
            {
                "billing_mode": "api",
                "costTotal": 1.23,
                "model": "gpt-6-luna",
                "inputTokens": 100,
                "outputTokens": 50,
            }
        )
        self.assertAlmostEqual(row["costTotal"], 1.23)


class LedgerAppendTest(unittest.TestCase):
    def test_malicious_project_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                with mock.patch("fsm_ledger.ledger.matrices_root", return_value=root):
                    result = append_dict(
                        {
                            "project": "../escape",
                            "model": "gpt-6-luna",
                            "event_id": "unsafe-project",
                            "cwd": str(root / "unknown"),
                        }
                    )
            self.assertTrue(result["ok"])
            self.assertEqual(result["project"], UNKNOWN_PROJECT)
            self.assertTrue((root / UNKNOWN_PROJECT / "usage.jsonl").exists())
            self.assertFalse((root.parent / "escape" / "usage.jsonl").exists())

    def test_unrelated_cwd_is_written_to_global_unknown_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": []}), encoding="utf-8"
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                with mock.patch("fsm_ledger.ledger.matrices_root", return_value=root):
                    result = append_dict(
                        {
                            "model": "gpt-6-luna",
                            "inputTokens": 10,
                            "outputTokens": 5,
                            "costTotal": 0.01,
                            "event_id": "unknown-cwd",
                            "cwd": str(root / "openai_finance"),
                        }
                    )
            self.assertTrue(result["ok"])
            self.assertEqual(result["project"], UNKNOWN_PROJECT)
            self.assertTrue((root / UNKNOWN_PROJECT / "usage.jsonl").exists())
            self.assertFalse((root / "agent-brain" / "usage.jsonl").exists())

    def test_append_dedupe_and_never_drop_spend(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": [str(root)], "remote_contains": "agent-brain"}),
                encoding="utf-8",
            )
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=root):
                with mock.patch("fsm_ledger.ledger.matrices_root", return_value=root):
                    r1 = append_dict(
                        {
                            "workPackageId": "AB-033",
                            "model": "gpt-6-luna",
                            "inputTokens": 1000,
                            "outputTokens": 100,
                            "costTotal": 0.05,
                            "event_id": "e1",
                            "message_id": "m1",
                            "harness": "test",
                            "cwd": str(root),
                        },
                        project="agent-brain",
                    )
                    r2 = append_dict(
                        {
                            "workPackageId": "AB-033",
                            "model": "gpt-6-luna",
                            "inputTokens": 1000,
                            "outputTokens": 100,
                            "costTotal": 0.05,
                            "event_id": "e1",
                            "message_id": "m1",
                            "harness": "test",
                            "cwd": str(root),
                        },
                        project="agent-brain",
                    )
                    r3 = append_dict(
                        {
                            "workPackageId": UNALLOCATED,
                            "model": "gpt-6-luna",
                            "inputTokens": 500,
                            "outputTokens": 50,
                            "costTotal": 0.02,
                            "event_id": "e2",
                            "message_id": "m2",
                            "harness": "test",
                            "cwd": str(root),
                        },
                        project="agent-brain",
                    )
            self.assertTrue(r1["ok"] and not r1.get("deduped"))
            self.assertTrue(r2["ok"] and r2.get("deduped"))
            self.assertTrue(r3["ok"] and not r3.get("deduped"))
            lines = (root / "agent-brain" / "usage.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)


class CodexHookTest(unittest.TestCase):
    def test_rollout_records_each_response_once(self):
        hook = SKILL / "harnesses" / "codex" / ".codex-plugin" / "fsm-ledger-hook"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": [str(root)]}), encoding="utf-8"
            )
            transcript = root / "rollout.jsonl"
            rows = [
                {"type": "session_meta", "payload": {"session_id": "s1", "cwd": str(root)}},
                {"type": "turn_context", "payload": {"turn_id": "t1", "model": "gpt-6-sol", "cwd": str(root)}},
                {"type": "token_usage_record", "timestamp": "2026-09-28T01:02:03Z", "payload": {
                    "response_id": "r1", "session_id": "s1", "turn_id": "t1", "usage": {
                        "input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 40,
                        "cache_write_input_tokens": 10, "total_tokens": 120,
                    }}},
                {"type": "token_usage_record", "timestamp": "2026-09-28T01:02:04Z", "payload": {
                    "response_id": "r2", "session_id": "s1", "turn_id": "t1", "usage": {
                        "input_tokens": 110, "output_tokens": 30, "cached_input_tokens": 50,
                        "cache_write_input_tokens": 0, "total_tokens": 140,
                    }}},
            ]
            transcript.write_text("\n".join(map(json.dumps, rows)) + "\n", encoding="utf-8")
            env = os.environ.copy()
            env.update({"FSM_MATRICES_ROOT": str(root), "FSM_PROJECT": "agent-brain"})
            payload = json.dumps({"transcript_path": str(transcript), "session_id": "s1", "cwd": str(root),
                                  "usage": {"input_tokens": 210, "output_tokens": 50}})
            for _ in range(2):
                proc = subprocess.run([str(hook), "stop"], input=payload, text=True,
                                      capture_output=True, env=env, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            stored = [json.loads(line) for line in (root / "agent-brain" / "usage.jsonl").read_text().splitlines()]
            self.assertEqual(len(stored), 2)
            self.assertEqual([row["event_id"] for row in stored], ["codex:s1:r1", "codex:s1:r2"])
            self.assertEqual(stored[0]["cacheWriteInputTokens"], 10)
            self.assertEqual(stored[0]["model"], "gpt-6-sol")
            self.assertEqual(stored[0]["ts"], "2026-09-28T01:02:03Z")

    def test_missing_rollout_keeps_hook_payload_for_retry(self):
        hooks = [
            SKILL / "harnesses" / "codex" / ".codex-plugin" / "fsm-ledger-hook",
            SKILL / "harnesses" / "codex-marketplace" / "plugins" / "fsm-ledger" / ".codex-plugin" / "fsm-ledger-hook",
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": [str(root)], "remote_contains": ""}),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update({"FSM_MATRICES_ROOT": str(root), "FSM_PROJECT": "agent-brain"})
            for index, hook in enumerate(hooks):
                proc = subprocess.run(
                    [str(hook), "stop"],
                    input=json.dumps(
                        {
                            "session_id": f"missing-{index}",
                            "cwd": str(root),
                        }
                    ),
                    text=True,
                    capture_output=True,
                    env=env,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((root / "agent-brain" / "usage.jsonl").exists())
            self.assertEqual(len(list((root / "_hook_pending").glob("event-*"))), len(hooks))


class ClaudeHookTest(unittest.TestCase):
    def test_transcript_keeps_final_usage_per_api_message(self):
        hook = SKILL / "harnesses" / "claude" / "stop_hook.py"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": [str(root)]}), encoding="utf-8"
            )
            transcript = root / "claude.jsonl"
            rows = [
                {"type": "assistant", "uuid": "u1", "timestamp": "2026-09-28T01:02:03Z", "message": {
                    "id": "msg_1", "model": "claude-sonnet-4-5", "usage": {"input_tokens": 5, "output_tokens": 2,
                    "cache_read_input_tokens": 40, "cache_creation_input_tokens": 10}}},
                {"type": "assistant", "uuid": "u2", "timestamp": "2026-09-28T01:02:04Z", "message": {
                    "id": "msg_1", "model": "claude-sonnet-4-5", "usage": {"input_tokens": 5, "output_tokens": 8,
                    "cache_read_input_tokens": 40, "cache_creation_input_tokens": 10}}},
            ]
            transcript.write_text("\n".join(map(json.dumps, rows)) + "\n", encoding="utf-8")
            env = os.environ.copy()
            env.update({"FSM_MATRICES_ROOT": str(root), "FSM_PROJECT": "agent-brain"})
            payload = json.dumps({"transcript_path": str(transcript), "session_id": "s1", "cwd": str(root),
                                  "usage": {"input_tokens": 5, "output_tokens": 8}})
            for _ in range(2):
                proc = subprocess.run([sys.executable, str(hook)], input=payload, text=True,
                                      capture_output=True, env=env, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            stored = [json.loads(line) for line in (root / "agent-brain" / "usage.jsonl").read_text().splitlines()]
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["event_id"], "claude:s1:msg_1")
            self.assertEqual(stored[0]["inputTokens"], 55)
            self.assertEqual(stored[0]["outputTokens"], 8)
            self.assertEqual(stored[0]["cachedInputTokens"], 40)
            self.assertEqual(stored[0]["cacheWriteInputTokens"], 10)
            self.assertEqual(stored[0]["ts"], "2026-09-28T01:02:04Z")


class PiHookTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node unavailable")
    def test_message_end_captures_all_usage_components(self):
        extension = SKILL / "harnesses" / "pi" / "extensions" / "fsm-ledger.ts"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": [str(root)]}), encoding="utf-8"
            )
            script = """
                const {default: extension} = await import(process.argv[1]);
                let handler;
                extension({on: (_name, fn) => { handler = fn; }});
                await handler({message: {id: 'm1', model: 'deepseek-v4-pro', timestamp: Date.parse('2026-09-28T01:02:03Z'),
                    usage: {input: 5, output: 8, cacheRead: 40, cacheWrite: 10}}},
                    {sessionManager: {getSessionId: () => 's1'}, cwd: process.argv[2], model: {provider: 'deepseek'}});
                await handler({message: {id: 'm1', model: 'deepseek-v4-pro', timestamp: Date.parse('2026-09-28T01:02:04Z'),
                    usage: {input: 5, output: 8, cacheRead: 40, cacheWrite: 10}}},
                    {sessionManager: {getSessionId: () => 's2'}, cwd: process.argv[2], model: {provider: 'deepseek'}});
            """
            env = os.environ.copy()
            env.update({"FSM_MATRICES_ROOT": str(root), "FSM_PROJECT": "agent-brain"})
            proc = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", script,
                                   str(extension), str(root)], capture_output=True, text=True, env=env, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            stored = [json.loads(line) for line in (root / "agent-brain" / "usage.jsonl").read_text().splitlines()]
            self.assertEqual(len(stored), 2)
            self.assertEqual({row["event_id"] for row in stored}, {"pi:s1:m1", "pi:s2:m1"})
            self.assertEqual(stored[0]["inputTokens"], 55)
            self.assertEqual(stored[0]["outputTokens"], 8)
            self.assertEqual(stored[0]["cachedInputTokens"], 40)
            self.assertEqual(stored[0]["cacheWriteInputTokens"], 10)
            self.assertEqual(stored[0]["ts"], "2026-09-28T01:02:03.000Z")


class CompactRenderTest(unittest.TestCase):
    def setUp(self):
        self.packages = [
            {"id": "AB-033", "theme": "Enrich-S3", "wave": 1, "size": "L", "title": "Videos", "state": "IN_PROGRESS"},
            {"id": "AB-034", "theme": "Enrich-S3", "wave": 1, "size": "M", "title": "Whisper", "state": "IN_PROGRESS"},
            {"id": "AB-001", "theme": "Platform", "wave": 1, "size": "L", "title": "Helix", "state": "ACCEPTED"},
        ]
        usage_jsonl = "\n".join(
            [
                json.dumps({"workPackageId": "AB-033", "costTotal": 1.5, "totalTokens": 1000, "status": "ok"}),
                json.dumps({"workPackageId": UNALLOCATED, "costTotal": 0.25, "totalTokens": 200, "status": "ok"}),
            ]
        )
        self.usage = aggregate_usage(usage_jsonl)
        self.budget = {"S": 2.0, "M": 5.0, "L": 15.0}

    def test_compact_shows_only_target_area_detail(self):
        md = render_markdown(
            self.packages,
            self.usage,
            self.budget,
            prior_state={"AB-033": {"status": "READY", "cost": 0.0}},
            mode="compact",
            area="Enrich-S3",
        )
        self.assertIn("Summary by Area", md)
        self.assertIn("### Enrich-S3", md)
        self.assertIn("### Delta", md)
        self.assertIn("AB-033", md)
        # Platform detail heading should not appear in compact when area=Enrich-S3
        self.assertNotIn("### Platform", md)

    def test_unallocated_synthetic_row(self):
        md = render_markdown(self.packages, self.usage, self.budget, mode="full")
        self.assertIn(UNALLOCATED, md)
        self.assertIn("Unallocated", md)

    def test_packages_json_loader(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "work-packages.json"
            path.write_text(
                json.dumps({"packages": self.packages}),
                encoding="utf-8",
            )
            loaded = load_packages_json(path)
            self.assertEqual(len(loaded), 3)
            self.assertEqual(loaded[0]["state"], "IN_PROGRESS")


if __name__ == "__main__":
    unittest.main()

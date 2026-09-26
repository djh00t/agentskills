"""Unit tests for fsm_ledger (append, attribute, pricer) + compact render."""
from __future__ import annotations

import json
import os
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
                    wp = resolve_work_package(cwd="/tmp", project="agent-brain")
                    self.assertEqual(wp, "AB-033")

    def test_basename_heuristic_agent_brain(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("fsm_ledger.attribute.matrices_root", return_value=Path(td)):
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("FSM_PROJECT", None)
                    os.environ.pop("FEATURE_PROJECT", None)
                    p = resolve_project(cwd="/Users/djh/work/src/github.com_local/djh00t/agent-brain")
                    self.assertEqual(p, "agent-brain")


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
    def test_append_dedupe_and_never_drop_spend(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent-brain").mkdir()
            (root / "agent-brain" / "project.json").write_text(
                json.dumps({"id": "agent-brain", "roots": [], "remote_contains": "agent-brain"}),
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

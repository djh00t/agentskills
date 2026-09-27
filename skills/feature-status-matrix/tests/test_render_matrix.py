"""Tests for the feature-status-matrix renderer (written before the implementation).

Covers the pure, reusable parts: usage aggregation (summing spend across every attempt,
including failed ones), budget lookup, state-file round-tripping, and the actual Markdown
render (summary-by-Area then detailed matrix, per the global reporting format), plus a
hermetic end-to-end test against a synthetic coordination.py-style fixture pack.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from render_matrix import (
    aggregate_usage,
    budget_for_size,
    compute_coordination_state,
    load_state,
    render_markdown,
    save_state,
)

USAGE_JSONL = "\n".join([
    json.dumps({"workPackageId": "WP-A", "status": "error", "totalTokens": 100, "costTotal": 0.0}),
    json.dumps({"workPackageId": "WP-A", "status": "accepted", "totalTokens": 900, "costTotal": 1.20}),
    json.dumps({"workPackageId": "WP-B", "status": "rejected", "totalTokens": 500, "costTotal": 0.60}),
])

BUDGET_POLICY = {"S": 2.0, "M": 5.0, "L": 15.0}


class AggregateUsageTest(unittest.TestCase):
    def test_sums_cost_and_tokens_across_every_attempt_including_failed(self):
        agg = aggregate_usage(USAGE_JSONL)
        self.assertEqual(agg["WP-A"].attempts, 2)
        self.assertAlmostEqual(agg["WP-A"].total_cost, 1.20)  # 0.0 (error) + 1.20 (accepted)
        self.assertEqual(agg["WP-A"].total_tokens, 1000)
        self.assertEqual(agg["WP-A"].last_status, "accepted")

    def test_missing_wp_has_zero_usage(self):
        agg = aggregate_usage(USAGE_JSONL)
        self.assertNotIn("WP-ZZZ", agg)

    def test_ignores_malformed_lines(self):
        agg = aggregate_usage("not json\n" + USAGE_JSONL)
        self.assertEqual(agg["WP-B"].attempts, 1)


class BudgetTest(unittest.TestCase):
    def test_looks_up_by_size(self):
        self.assertEqual(budget_for_size("S", BUDGET_POLICY), 2.0)
        self.assertEqual(budget_for_size("L", BUDGET_POLICY), 15.0)

    def test_unknown_size_defaults_to_largest_budget_conservatively(self):
        self.assertEqual(budget_for_size("XL", BUDGET_POLICY), 15.0)


class StateFileTest(unittest.TestCase):
    def test_round_trips_and_defaults_when_absent(self):
        tmp = Path(tempfile.mkdtemp()) / "status-matrix-state.json"
        self.assertEqual(load_state(tmp), {})
        save_state(tmp, {"WP-A": {"status": "accepted", "cost": 1.2}})
        self.assertEqual(load_state(tmp)["WP-A"]["status"], "accepted")


class RenderMarkdownTest(unittest.TestCase):
    def setUp(self):
        self.packages = [
            {"id": "WP-A", "theme": "GOV", "wave": 0, "size": "S", "title": "Import pack", "state": "ACCEPTED"},
            {"id": "WP-B", "theme": "GOV", "wave": 0, "size": "L", "title": "Scaffold UI", "state": "REJECTED"},
            {"id": "WP-C", "theme": "DOM", "wave": 4, "size": "M", "title": "Core ids", "state": "BLOCKED"},
        ]
        self.usage = aggregate_usage(USAGE_JSONL)

    def test_summary_appears_before_detailed_matrix(self):
        md = render_markdown(self.packages, self.usage, BUDGET_POLICY, prior_state={})
        self.assertLess(md.index("Summary"), md.index("Detailed"))

    def test_groups_by_area_and_shows_emoji_and_percent(self):
        md = render_markdown(self.packages, self.usage, BUDGET_POLICY, prior_state={})
        self.assertIn("GOV", md)
        self.assertIn("DOM", md)
        self.assertIn("100%", md)   # accepted
        self.assertIn("✅", md)
        self.assertIn("⚪", md)     # blocked/not-started

    def test_shows_budget_actual_and_delta_columns(self):
        md = render_markdown(self.packages, self.usage, BUDGET_POLICY, prior_state={})
        self.assertIn("Budget", md)
        self.assertIn("Actual", md)
        self.assertIn("$1.20", md)   # WP-A actual
        self.assertIn("$2.00", md)   # WP-A budget (size S)

    def test_flags_changed_status_since_prior_snapshot(self):
        prior = {"WP-A": {"status": "IN_PROGRESS"}}
        md = render_markdown(self.packages, self.usage, BUDGET_POLICY, prior_state=prior)
        self.assertIn("changed", md.lower())


COORD_TOOL_SRC = Path.home() / "work/src/github.com/djh00t/to2/tools/coordination.py"


def build_fixture_pack(root: Path):
    (root / "tools").mkdir(parents=True)
    for sub in ("claims", "heartbeats", "deliveries"):
        (root / "coordination" / sub).mkdir(parents=True)
    (root / "delivery" / "work-packages").mkdir(parents=True)
    packages = [
        {"id": "WP-A", "title": "A", "theme": "GOV", "wave": 0, "size": "S", "dependencies": [],
         "workPackageFile": "delivery/work-packages/WP-A.md"},
        {"id": "WP-B", "title": "B", "theme": "GOV", "wave": 1, "size": "M", "dependencies": ["WP-A"],
         "workPackageFile": "delivery/work-packages/WP-B.md"},
    ]
    (root / "coordination" / "work-packages.json").write_text(
        json.dumps({"specRevision": "t", "packages": packages}), encoding="utf-8")
    for p in packages:
        (root / p["workPackageFile"]).write_text("# " + p["id"], encoding="utf-8")
    (root / "coordination" / "deliveries" / "WP-A.json").write_text(
        json.dumps({"status": "accepted"}), encoding="utf-8")


@unittest.skipUnless(COORD_TOOL_SRC.is_file(), "reference coordination.py not found; skipping live-schema check")
class CoordinationStateIntegrationTest(unittest.TestCase):
    def test_reads_real_coordination_layout(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            build_fixture_pack(tmp)
            packages = compute_coordination_state(tmp)
            by_id = {p["id"]: p for p in packages}
            self.assertEqual(by_id["WP-A"]["state"], "ACCEPTED")
            self.assertEqual(by_id["WP-B"]["state"], "READY")  # dep accepted, no claim yet
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

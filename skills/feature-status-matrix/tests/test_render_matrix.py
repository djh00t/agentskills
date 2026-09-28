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
    load_packages_json,
    render_markdown,
    detect_changed_areas,
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

    def test_marks_missing_and_partial_telemetry_as_unknown(self):
        md = render_markdown(self.packages, {}, BUDGET_POLICY, prior_state={})
        self.assertIn("| GOV |", md)
        self.assertIn("| GOV | 🟡 | 70% | $17.00 | — |", md)
        self.assertIn("| **TOTAL** | | | **$22.00** | **—** |", md)
        self.assertIn("| WP-A | Import pack | 0 | S | ✅🟢 | 100% | $2.00 | — | — |", md)

        partial = render_markdown(self.packages, self.usage, BUDGET_POLICY, prior_state={})
        self.assertIn("partial $1.80", partial)

    def test_marks_estimated_costs_distinctly(self):
        usage = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "totalTokens": 100, "costTotal": 1.2,
            "cost_estimated": True,
        }))
        md = render_markdown(self.packages, usage, BUDGET_POLICY, prior_state={})
        self.assertIn("~$1.20", md)
        self.assertIn("~$-0.80", md)

    def test_renders_explicit_zero_provider_cost_as_measured(self):
        usage = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "costTotal": 0.0,
        }))
        self.assertEqual(usage["WP-A"].measured_attempts, 1)
        self.assertEqual(usage["WP-A"].unknown_attempts, 0)
        md = render_markdown(self.packages, usage, BUDGET_POLICY, prior_state={})
        self.assertIn("| WP-A | Import pack | 0 | S | ✅🟢 | 100% | $2.00 | $0.00 | $-2.00 |", md)

    def test_compact_delta_includes_new_package_without_legacy_flood(self):
        packages = self.packages + [
            {"id": "WP-NEW", "theme": "NEW", "wave": 1, "size": "S",
             "title": "New package", "state": "READY"},
            {"id": "WP-NEW-2", "theme": "NEW", "wave": 2, "size": "M",
             "title": "Second new package", "state": "READY"},
        ]
        prior = {
            "WP-A": {"status": "ACCEPTED", "cost": 0.0},
            "WP-B": {"status": "REJECTED", "cost": 0.0},
            "WP-C": {"status": "BLOCKED", "cost": 0.0},
        }
        self.assertEqual(detect_changed_areas(packages, prior, {}), ["NEW"])
        md = render_markdown(packages, {}, BUDGET_POLICY, prior, mode="compact")
        self.assertIn("### NEW", md)
        self.assertIn("- WP-NEW · new package", md)
        self.assertIn("- WP-NEW-2 · new package", md)
        self.assertNotIn("- WP-A", md)
        self.assertNotIn("- WP-B", md)
        self.assertNotIn("- WP-C", md)

    def test_keeps_unknown_and_plan_costs_out_of_numeric_delta(self):
        unknown = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "totalTokens": 100,
        }))
        md = render_markdown(self.packages, unknown, BUDGET_POLICY, prior_state={})
        self.assertIn("| WP-A | Import pack | 0 | S | ✅🟢 | 100% | $2.00 | unknown | — |", md)

        plan = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "billing_mode": "subscription",
        }))
        md = render_markdown(self.packages, plan, BUDGET_POLICY, prior_state={})
        self.assertIn("| WP-A | Import pack | 0 | S | ✅🟢 | 100% | $2.00 | plan | — |", md)

        mixed = aggregate_usage("\n".join([
            json.dumps({"workPackageId": "WP-A", "costTotal": 1.0, "cost_estimated": True}),
            json.dumps({"workPackageId": "WP-A", "billing_mode": "subscription"}),
        ]))
        md = render_markdown(self.packages, mixed, BUDGET_POLICY, prior_state={})
        self.assertIn("~$1.00+plan", md)
        self.assertIn("partial ~$1.00+plan", md)

    def test_compact_delta_uses_actual_provenance(self):
        estimated = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "costTotal": 1.2, "cost_estimated": True,
        }))
        prior = {
            "WP-A": {"status": "ACCEPTED", "cost": 0.0, "actual": "$0.00"},
            "WP-B": {"status": "REJECTED", "cost": 0.0, "actual": "—"},
            "WP-C": {"status": "BLOCKED", "cost": 0.0, "actual": "—"},
        }
        md = render_markdown(self.packages, estimated, BUDGET_POLICY, prior, mode="compact", area="GOV")
        self.assertIn("actual $0.00→~$1.20", md)
        self.assertNotIn("cost $0.00→$1.20", md)

        plan = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "billing_mode": "subscription",
        }))
        prior["WP-A"]["actual"] = "—"
        self.assertEqual(detect_changed_areas(self.packages, prior, plan), ["GOV"])
        md = render_markdown(self.packages, plan, BUDGET_POLICY, prior, mode="compact", area="GOV")
        self.assertIn("actual —→plan", md)

    def test_legacy_zero_cost_state_detects_provenance_changes(self):
        prior = {
            "WP-A": {"status": "ACCEPTED", "cost": 0.0},
            "WP-B": {"status": "REJECTED", "cost": 0.0},
            "WP-C": {"status": "BLOCKED", "cost": 0.0},
        }
        self.assertEqual(detect_changed_areas(self.packages, prior, {}), [])
        md = render_markdown(self.packages, {}, BUDGET_POLICY, prior, mode="compact", area="GOV")
        self.assertIn("_No changes since last snapshot._", md)

        estimated = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "costTotal": 1.2, "cost_estimated": True,
        }))
        md = render_markdown(self.packages, estimated, BUDGET_POLICY, prior, mode="compact", area="GOV")
        self.assertIn("actual legacy→~$1.20", md)

        plan = aggregate_usage(json.dumps({
            "workPackageId": "WP-A", "billing_mode": "subscription",
        }))
        md = render_markdown(self.packages, plan, BUDGET_POLICY, prior, mode="compact", area="GOV")
        self.assertIn("actual legacy→plan", md)

        unknown = aggregate_usage(json.dumps({"workPackageId": "WP-A", "totalTokens": 100}))
        self.assertEqual(detect_changed_areas(self.packages, prior, unknown), ["GOV"])

    def test_flags_changed_status_since_prior_snapshot(self):
        prior = {"WP-A": {"status": "IN_PROGRESS"}}
        md = render_markdown(self.packages, self.usage, BUDGET_POLICY, prior_state=prior)
        self.assertIn("changed", md.lower())

    def test_compact_detail_includes_escaped_wp_title(self):
        packages = [{
            "id": "WP-TITLE", "theme": "GOV", "wave": 1, "size": "S",
            "title": "Compact | title\nwith line", "state": "IN_PROGRESS",
        }]
        md = render_markdown(packages, {}, BUDGET_POLICY, mode="compact", area="GOV")
        self.assertIn("Name/description", md)
        self.assertIn("Compact \\| title<br>with line", md)

        full_md = render_markdown(packages, {}, BUDGET_POLICY, mode="full")
        self.assertIn("Name/description", full_md)
        self.assertIn("Compact \\| title<br>with line", full_md)

    def test_renders_package_note_with_status_change_and_markdown_escaping(self):
        package = [{
            "id": "AB-052.3", "theme": "Social", "wave": 1, "size": "S",
            "title": "Archive account", "state": "BLOCKED",
            "note": "Approval | rejected\nno account data fetched.",
        }]
        md = render_markdown(
            package, {}, BUDGET_POLICY,
            prior_state={"AB-052.3": {"status": "IN_PROGRESS"}},
        )
        self.assertIn(
            "Approval \\| rejected<br>no account data fetched.; "
            "changed: IN_PROGRESS→BLOCKED",
            md,
        )

    def test_load_packages_json_preserves_package_note(self):
        path = Path(tempfile.mkdtemp()) / "work-packages.json"
        try:
            path.write_text(json.dumps({"packages": [{
                "id": "AB-052.3", "theme": "Social", "wave": 1, "size": "S",
                "title": "Archive account", "state": "BLOCKED", "note": "blocked",
            }]}), encoding="utf-8")
            self.assertEqual(load_packages_json(path)[0]["note"], "blocked")
        finally:
            shutil.rmtree(path.parent, ignore_errors=True)


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

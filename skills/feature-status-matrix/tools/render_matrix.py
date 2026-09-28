#!/usr/bin/env python3
"""Feature Status Matrix renderer.

Generates the standard summary-by-Area + detailed-matrix report (see SKILL.md) for any
project that tracks work items with an Area/Theme, a size, and a status, optionally with
per-item token/cost telemetry (JSONL) to show budget vs. actual spend.

Designed against the coordination.py claim-protocol pattern (work-packages.json + claims/
heartbeats/deliveries directories) that spec-pack tooling like the to2 Thread Orchestrator
pack generates, but the rendering itself works from a plain list of package dicts so it can
be adapted to other state sources.

Also supports --packages-json (agent-brain layout with state already on each package) and
--mode full|compact.

Dependency-free (stdlib only), matching the target packs' own tooling conventions.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

DEFAULT_BUDGET_POLICY = {"S": 2.0, "M": 5.0, "L": 15.0}

# Standard progress-% convention for coordination.py-style states (documented in SKILL.md so
# every project using this skill reports percentages consistently, not by feel).
STATUS_PROGRESS = {
    "ACCEPTED": 100, "DELIVERED": 70, "IN_PROGRESS": 50, "CLAIMED": 30,
    "REJECTED": 40, "READY": 0, "BLOCKED": 0,
}
STATUS_EMOJI = {
    "ACCEPTED": "✅🟢", "DELIVERED": "🔵", "IN_PROGRESS": "🔵", "CLAIMED": "🔵",
    "REJECTED": "🟡", "READY": "⚪", "BLOCKED": "⚪",
}

UNALLOCATED = "UNALLOCATED"


@dataclass
class UsageAgg:
    total_cost: float = 0.0
    estimated_cost: float = 0.0
    total_tokens: int = 0
    attempts: int = 0
    estimated_attempts: int = 0
    measured_attempts: int = 0
    unknown_attempts: int = 0
    last_status: str = ""
    plan_events: int = 0


def aggregate_usage(jsonl_text: str) -> dict[str, UsageAgg]:
    """Sum cost/tokens across EVERY attempt for a work package, including failed ones --
    a rejected or errored attempt still spent real tokens and money."""
    out: dict[str, UsageAgg] = {}
    for line in (jsonl_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        wp_id = row.get("workPackageId")
        if not wp_id:
            continue
        agg = out.setdefault(wp_id, UsageAgg())
        cost = float(row.get("costTotal", 0.0) or 0.0)
        has_reported_cost = "costTotal" in row and row.get("costTotal") is not None
        is_plan = row.get("cost_is_plan") or str(row.get("billing_mode") or "").lower() == "subscription"
        if row.get("cost_estimated"):
            agg.total_cost += cost
            agg.estimated_cost += cost
            agg.estimated_attempts += 1
        elif is_plan:
            pass
        elif has_reported_cost:
            agg.total_cost += cost
            agg.measured_attempts += 1
        else:
            agg.unknown_attempts += 1
        agg.total_tokens += int(row.get("totalTokens", 0) or 0)
        agg.attempts += 1
        agg.last_status = row.get("status", agg.last_status)
        if row.get("cost_is_plan") or str(row.get("billing_mode") or "").lower() == "subscription":
            agg.plan_events += 1
    return out


def budget_for_size(size: str, policy: dict[str, float]) -> float:
    if size in policy:
        return policy[size]
    return max(policy.values()) if policy else 0.0


def load_state(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _pct(state: str) -> int:
    return STATUS_PROGRESS.get(state, 0)


def _emoji(state: str) -> str:
    return STATUS_EMOJI.get(state, "⚪")


def _fmt_actual(u: UsageAgg, reported: bool = True) -> str:
    if not reported:
        return "—"
    if u.plan_events and u.total_cost == 0.0 and u.attempts == u.plan_events:
        return "plan"
    parts: list[str] = []
    measured_cost = u.total_cost - u.estimated_cost
    if u.measured_attempts:
        parts.append(f"${measured_cost:.2f}")
    if u.estimated_attempts:
        parts.append(f"~${u.estimated_cost:.2f}")
    if u.plan_events:
        parts.append("plan")
    if u.unknown_attempts:
        parts.append("unknown")
    return "+".join(parts) or "—"


def _fmt_delta(u: UsageAgg, budget: float, reported: bool = True) -> str:
    if not reported or u.unknown_attempts or u.plan_events:
        return "—"
    prefix = "~" if u.estimated_attempts else ""
    return f"{prefix}${u.total_cost - budget:+.2f}"


def _aggregate_usage(pkgs: list[dict[str, Any]], usage: dict[str, UsageAgg]) -> tuple[UsageAgg, int]:
    aggregate = UsageAgg()
    reported = 0
    for p in pkgs:
        u = usage.get(p["id"])
        if u is None:
            continue
        reported += 1
        aggregate.total_cost += u.total_cost
        aggregate.estimated_cost += u.estimated_cost
        aggregate.total_tokens += u.total_tokens
        aggregate.attempts += u.attempts
        aggregate.estimated_attempts += u.estimated_attempts
        aggregate.measured_attempts += u.measured_attempts
        aggregate.unknown_attempts += u.unknown_attempts
        aggregate.plan_events += u.plan_events
    return aggregate, reported


def _actual_for_package(p: dict[str, Any], usage: dict[str, UsageAgg]) -> str:
    return _fmt_actual(usage.get(p["id"], UsageAgg()), p["id"] in usage)


def _prior_actual(prior: dict[str, Any]) -> str:
    if "actual" in prior:
        return str(prior["actual"])
    cost = float(prior.get("cost") or 0.0)
    return f"${cost:.2f}" if cost else "legacy"


def ensure_unallocated_package(
    packages: list[dict[str, Any]],
    usage: dict[str, UsageAgg],
) -> list[dict[str, Any]]:
    """Add a synthetic UNALLOCATED WP when usage log has it but packages don't."""
    if UNALLOCATED not in usage:
        return packages
    if any(p.get("id") == UNALLOCATED for p in packages):
        return packages
    return list(packages) + [
        {
            "id": UNALLOCATED,
            "theme": "Unallocated",
            "wave": "-",
            "size": "-",
            "title": "Usage not bound to a work package",
            "state": "READY",
        }
    ]


def _changed_note(p: dict[str, Any], prior_state: dict[str, Any], u: UsageAgg) -> str:
    note_parts: list[str] = []
    if p.get("note"):
        note_parts.append(str(p["note"]))
    prior = prior_state.get(p["id"])
    if prior and prior.get("status") and prior.get("status") != p["state"]:
        note_parts.append(f"changed: {prior['status']}\u2192{p['state']}")
    if u.attempts > 1:
        note_parts.append(f"{u.attempts} attempts")
    if u.plan_events:
        note_parts.append(f"{u.plan_events} plan")
    return "; ".join(note_parts)


def _markdown_cell(value: Any) -> str:
    return str(value or "-").replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>").replace("|", "\\|")


def _detail_rows(
    pkgs: list[dict[str, Any]],
    usage: dict[str, UsageAgg],
    budget_policy: dict[str, float],
    prior_state: dict[str, Any],
) -> list[str]:
    lines = [
        "| WP | Name/description | Wave | Size | Status | % | Budget | Actual | Δ | Note |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in sorted(pkgs, key=lambda x: x["id"]):
        reported = p["id"] in usage
        u = usage.get(p["id"], UsageAgg())
        size = str(p.get("size") or "-")
        budget = 0.0 if size == "-" else budget_for_size(size, budget_policy)
        note = _changed_note(p, prior_state, u)
        lines.append(
            f"| {p['id']} | {_markdown_cell(p.get('title'))} | {p['wave']} | {p['size']} | {_emoji(p['state'])} | {_pct(p['state'])}% | "
            f"${budget:.2f} | {_fmt_actual(u, reported)} | {_fmt_delta(u, budget, reported)} | {_markdown_cell(note)} |"
        )
    return lines


def _summary_lines(
    areas: dict[str, list[dict[str, Any]]],
    usage: dict[str, UsageAgg],
    budget_policy: dict[str, float],
) -> tuple[list[str], float, float]:
    lines = [
        "# Feature Status Matrix",
        "",
        "## Summary by Area",
        "",
        "| Area | Status | Progress | Budget | Actual |",
        "|---|---|---|---|---|",
    ]
    grand_budget = grand_actual = 0.0
    for area in sorted(areas):
        pkgs = areas[area]
        avg_pct = sum(_pct(p["state"]) for p in pkgs) / len(pkgs) if pkgs else 0.0
        area_budget = sum(
            0.0 if str(p.get("size") or "-") == "-" else budget_for_size(p["size"], budget_policy)
            for p in pkgs
        )
        area_usage, reported = _aggregate_usage(pkgs, usage)
        area_actual = area_usage.total_cost
        grand_budget += area_budget
        grand_actual += area_actual
        emoji = "✅🟢" if avg_pct >= 100 else ("🟡" if avg_pct > 0 else "⚪")
        if any(p["state"] in ("IN_PROGRESS", "CLAIMED") for p in pkgs) and avg_pct < 100:
            emoji = "🔵"
        actual = _fmt_actual(area_usage, reported > 0)
        if 0 < reported < len(pkgs):
            actual = f"partial {actual}"
        lines.append(f"| {area} | {emoji} | {avg_pct:.0f}% | ${area_budget:.2f} | {actual} |")
    total_usage, total_reported = _aggregate_usage(
        [p for pkgs in areas.values() for p in pkgs], usage
    )
    total_actual = _fmt_actual(total_usage, total_reported > 0)
    if 0 < total_reported < sum(len(pkgs) for pkgs in areas.values()):
        total_actual = f"partial {total_actual}"
    lines.append(f"| **TOTAL** | | | **${grand_budget:.2f}** | **{total_actual}** |")
    return lines, grand_budget, grand_actual


def detect_changed_areas(
    packages: list[dict[str, Any]],
    prior_state: dict[str, Any],
    usage: dict[str, UsageAgg],
) -> list[str]:
    changed: set[str] = set()
    missing_ids = [p["id"] for p in packages if p["id"] not in prior_state]
    new_package_ids = set(missing_ids) if prior_state else set()
    for p in packages:
        prior = prior_state.get(p["id"]) or {}
        if not prior:
            if p["id"] in new_package_ids:
                changed.add(p["theme"])
            continue
        if prior.get("status") and prior.get("status") != p["state"]:
            changed.add(p["theme"])
            continue
        legacy_missing = "actual" not in prior and not float(prior.get("cost") or 0.0) and p["id"] not in usage
        changed_actual = not legacy_missing and _prior_actual(prior) != _actual_for_package(p, usage)
        if changed_actual:
            changed.add(p["theme"])
    return sorted(changed)


def render_markdown(
    packages: list[dict[str, Any]],
    usage: dict[str, UsageAgg],
    budget_policy: dict[str, float],
    prior_state: Optional[dict[str, Any]] = None,
    *,
    mode: str = "full",
    area: Optional[str] = None,
) -> str:
    prior_state = prior_state or {}
    packages = ensure_unallocated_package(packages, usage)
    areas: dict[str, list[dict[str, Any]]] = {}
    for p in packages:
        areas.setdefault(p["theme"], []).append(p)

    summary, _, _ = _summary_lines(areas, usage, budget_policy)
    lines: list[str] = list(summary)

    if mode == "compact":
        target_areas: list[str]
        if area:
            target_areas = [area]
        else:
            target_areas = detect_changed_areas(packages, prior_state, usage)
            if not target_areas:
                # Fall back to first area with any usage, else first area
                with_usage = [a for a in sorted(areas) if any(usage.get(p["id"]) for p in areas[a])]
                target_areas = with_usage[:1] or (sorted(areas)[:1] if areas else [])

        lines += ["", "## Detailed Feature Matrix (compact)", ""]
        for a in target_areas:
            if a not in areas:
                lines += [f"### {a}", "", "_No packages in this area._", ""]
                continue
            lines += [f"### {a}", ""]
            lines += _detail_rows(areas[a], usage, budget_policy, prior_state)
            lines.append("")

        # Delta section
        lines += ["### Delta", ""]
        delta_lines: list[str] = []
        missing_ids = [p["id"] for p in packages if p["id"] not in prior_state]
        new_package_ids = set(missing_ids) if prior_state else set()
        for p in packages:
            prior = prior_state.get(p["id"]) or {}
            if not prior:
                if p["id"] in new_package_ids:
                    delta_lines.append(f"- {p['id']} · new package")
                continue
            u = usage.get(p["id"], UsageAgg())
            status_changed = prior.get("status") and prior.get("status") != p["state"]
            actual = _actual_for_package(p, usage)
            legacy_missing = "actual" not in prior and not float(prior.get("cost") or 0.0) and p["id"] not in usage
            actual_changed = not legacy_missing and _prior_actual(prior) != actual
            if status_changed or actual_changed:
                parts = [p["id"]]
                if status_changed:
                    parts.append(f"{prior.get('status')}→{p['state']}")
                if actual_changed:
                    parts.append(f"actual {_prior_actual(prior)}→{actual}")
                delta_lines.append("- " + " · ".join(parts))
        if not delta_lines:
            lines.append("_No changes since last snapshot._")
        else:
            lines.extend(delta_lines)
        lines.append("")
        return "\n".join(lines)

    # full mode
    lines += ["", "## Detailed Feature Matrix", ""]
    for a in sorted(areas):
        lines += [f"### {a}", ""]
        lines += _detail_rows(areas[a], usage, budget_policy, prior_state)
        lines.append("")
    return "\n".join(lines)


# --- coordination.py-schema state computation ------------------------------------------

def compute_coordination_state(pack_root: Path) -> list[dict[str, Any]]:
    pack_root = Path(pack_root)
    registry = json.loads((pack_root / "coordination" / "work-packages.json").read_text("utf-8"))
    packages = registry["packages"]

    def accepted(pid: str) -> bool:
        path = pack_root / "coordination" / "deliveries" / f"{pid}.json"
        if not path.exists():
            return False
        try:
            return json.loads(path.read_text("utf-8")).get("status") == "accepted"
        except (OSError, json.JSONDecodeError):
            return False

    def state_for(pkg: dict[str, Any]) -> str:
        pid = pkg["id"]
        dpath = pack_root / "coordination" / "deliveries" / f"{pid}.json"
        if dpath.exists():
            try:
                return json.loads(dpath.read_text("utf-8")).get("status", "delivered").upper()
            except (OSError, json.JSONDecodeError):
                return "DELIVERED"
        cpath = pack_root / "coordination" / "claims" / f"{pid}.json"
        if cpath.exists():
            hpath = pack_root / "coordination" / "heartbeats" / f"{pid}.json"
            if hpath.exists():
                try:
                    return json.loads(hpath.read_text("utf-8")).get("state", "claimed").upper()
                except (OSError, json.JSONDecodeError):
                    return "CLAIMED"
            return "CLAIMED"
        if all(accepted(dep) for dep in pkg.get("dependencies", [])):
            return "READY"
        return "BLOCKED"

    return [
        {"id": p["id"], "theme": p["theme"], "wave": p["wave"], "size": p["size"],
         "title": p["title"], "state": state_for(p), "note": p.get("note", "")}
        for p in packages
    ]


def load_packages_json(path: Path) -> list[dict[str, Any]]:
    """Load agent-brain-style work-packages.json (state already on each package)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    packages = data.get("packages") if isinstance(data, dict) else data
    if not isinstance(packages, list):
        raise ValueError(f"packages-json must contain a packages list: {path}")
    out: list[dict[str, Any]] = []
    for p in packages:
        out.append(
            {
                "id": p["id"],
                "theme": p.get("theme") or p.get("area") or "Unknown",
                "wave": p.get("wave", "-"),
                "size": p.get("size", "M"),
                "title": p.get("title", ""),
                "state": str(p.get("state") or p.get("status") or "READY").upper(),
                "note": p.get("note", ""),
            }
        )
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pack-root", default=None, help="Root of a coordination.py-style pack.")
    src.add_argument(
        "--packages-json",
        default=None,
        help="Path to work-packages.json with state already on each package.",
    )
    ap.add_argument("--usage-log", default=None, help="JSONL file with per-item token/cost telemetry.")
    ap.add_argument("--state-file", default=None, help="Project-specific snapshot state file (for change tracking).")
    ap.add_argument("--budget-policy", default=None, help="JSON file mapping size -> budget USD.")
    ap.add_argument("--out", default=None, help="Always refresh full markdown here when given.")
    ap.add_argument("--mode", choices=("full", "compact"), default="full")
    ap.add_argument(
        "--area",
        default=None,
        help="Area/theme for compact detail (auto-detect from prior_state deltas if omitted).",
    )
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.packages_json:
        packages = load_packages_json(Path(args.packages_json))
    else:
        packages = compute_coordination_state(Path(args.pack_root))

    usage_text = Path(args.usage_log).read_text("utf-8") if args.usage_log and Path(args.usage_log).exists() else ""
    usage = aggregate_usage(usage_text)
    budget_policy = (
        json.loads(Path(args.budget_policy).read_text("utf-8")) if args.budget_policy else DEFAULT_BUDGET_POLICY
    )
    state_path = Path(args.state_file) if args.state_file else None
    prior_state = load_state(state_path) if state_path else {}

    if args.mode == "compact" and not args.area:
        # allowed: auto-detect; only error if caller required area and nothing moved —
        # we soft-fallback inside render_markdown
        pass

    view = render_markdown(
        packages, usage, budget_policy, prior_state, mode=args.mode, area=args.area
    )

    # Always refresh full file on disk when --out given
    if args.out:
        full_md = render_markdown(
            packages, usage, budget_policy, prior_state, mode="full", area=None
        )
        Path(args.out).write_text(full_md, encoding="utf-8")

    if state_path:
        packages_with_ua = ensure_unallocated_package(packages, usage)
        new_state = {
            p["id"]: {
                "status": p["state"],
                "cost": usage.get(p["id"], UsageAgg()).total_cost,
                "actual": _actual_for_package(p, usage),
            }
            for p in packages_with_ua
        }
        save_state(state_path, new_state)

    # Print mode-selected view to stdout (even when --out wrote full file)
    print(view)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

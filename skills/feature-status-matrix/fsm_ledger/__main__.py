"""CLI: python3 -m fsm_ledger <subcommand>"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .attribute import bind_active_wp, resolve_attribution
from .install import install as do_install
from .install import uninstall as do_uninstall
from .ledger import append_dict, usage_log_path
from .render_trigger import render_now, schedule_render
from .schema import UNALLOCATED


def _cmd_append(args: argparse.Namespace) -> int:
    if args.json:
        raw = json.loads(args.json)
    else:
        text = sys.stdin.read()
        if not text.strip():
            print(json.dumps({"ok": False, "error": "empty stdin / --json"}), file=sys.stderr)
            return 1
        raw = json.loads(text)
    if args.project:
        raw["project"] = args.project
    if args.wp:
        raw["workPackageId"] = args.wp
    if args.harness:
        raw["harness"] = args.harness
    result = append_dict(raw, project=args.project)
    print(json.dumps(result))
    if args.render and result.get("ok") and not result.get("deduped"):
        schedule_render(result.get("project") or args.project or "agent-brain")
    return 0 if result.get("ok") else 1


def _cmd_install(args: argparse.Namespace) -> int:
    names = [n.strip() for n in args.harnesses.split(",") if n.strip()]
    results = do_install(names)
    print(json.dumps(results, indent=2))
    return 0 if all(r.get("ok", True) for r in results if "harness" in r) else 1


def _cmd_uninstall(args: argparse.Namespace) -> int:
    names = None
    if args.harnesses:
        names = [n.strip() for n in args.harnesses.split(",") if n.strip()]
    results = do_uninstall(names)
    print(json.dumps(results, indent=2))
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    result = render_now(args.project, mode=args.mode, area=args.area)
    if result.get("stdout"):
        print(result["stdout"], end="" if result["stdout"].endswith("\n") else "\n")
    if not result.get("ok"):
        print(json.dumps({"ok": False, "error": result.get("error")}), file=sys.stderr)
        return 1
    return 0


def _cmd_bind_wp(args: argparse.Namespace) -> int:
    path = bind_active_wp(args.project, args.wp)
    print(json.dumps({"ok": True, "path": str(path), "project": args.project, "workPackageId": args.wp}))
    return 0


def _cmd_smoke(args: argparse.Namespace) -> int:
    """Append fixture rows (labeled) + render compact and full."""
    project = args.project
    rows = [
        {
            "workPackageId": "AB-033",
            "model": "gpt-6-luna",
            "inputTokens": 2_500_000,
            "outputTokens": 400_000,
            "cachedInputTokens": 500_000,
            "costTotal": 1.25,  # fixture-smoke explicit
            "harness": "smoke",
            "provider": "openai",
            "status": "fixture-smoke",
            "billing_mode": "api",
            "event_id": "smoke-ab033-002",
            "message_id": "smoke-msg-ab033-002",
            "cwd": "/Users/djh/work/src/github.com_local/djh00t/agent-brain",
        },
        {
            "workPackageId": UNALLOCATED,
            "model": "gpt-6-luna",
            "inputTokens": 800_000,
            "outputTokens": 100_000,
            "costTotal": 0.35,  # fixture-smoke explicit
            "harness": "smoke",
            "provider": "openai",
            "status": "fixture-smoke",
            "billing_mode": "api",
            "event_id": "smoke-unalloc-002",
            "message_id": "smoke-msg-unalloc-002",
            "cwd": "/Users/djh/work/src/github.com_local/djh00t/agent-brain",
        },
        {
            "workPackageId": "AB-033",
            "model": "gpt-6-sol",
            "inputTokens": 1000,
            "outputTokens": 200,
            "harness": "smoke",
            "status": "fixture-smoke",
            "billing_mode": "subscription",
            "event_id": "smoke-ab033-plan-002",
            "message_id": "smoke-msg-ab033-plan-002",
            "cwd": "/Users/djh/work/src/github.com_local/djh00t/agent-brain",
        },
    ]
    results = []
    for row in rows:
        results.append(append_dict(row, project=project))
    compact = render_now(project, mode="compact", area="Enrich-S3")
    full = render_now(project, mode="full")
    out = {
        "ok": all(r.get("ok") for r in results) and compact.get("ok") and full.get("ok"),
        "appends": results,
        "usage_log": str(usage_log_path(project)),
        "compact_ok": compact.get("ok"),
        "full_ok": full.get("ok"),
        "matrix": full.get("out"),
        "note": "fixture-smoke rows — not real spend",
    }
    print(json.dumps(out, indent=2))
    if compact.get("stdout"):
        print("\n--- compact stdout (snippet) ---")
        print("\n".join(compact["stdout"].splitlines()[:40]))
    return 0 if out["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fsm_ledger", description="Shared usage ledger for feature-status-matrix")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("append", help="Append a usage event (JSON stdin or --json)")
    p.add_argument("--json", default=None)
    p.add_argument("--project", default=None)
    p.add_argument("--wp", default=None)
    p.add_argument("--harness", default=None)
    p.add_argument("--render", action="store_true", help="Render after append in an independent process")
    p.set_defaults(func=_cmd_append)

    p = sub.add_parser("install", help="Install harness hooks")
    p.add_argument("--harnesses", required=True, help="Comma list: codex,claude,pi,opencode")
    p.set_defaults(func=_cmd_install)

    p = sub.add_parser("uninstall", help="Remove fsm-ledger harness hooks")
    p.add_argument("--harnesses", default=None)
    p.set_defaults(func=_cmd_uninstall)

    p = sub.add_parser("render", help="Render status matrix for a project")
    p.add_argument("--project", required=True)
    p.add_argument("--mode", choices=("full", "compact"), default="full")
    p.add_argument("--area", default=None)
    p.set_defaults(func=_cmd_render)

    p = sub.add_parser("bind-wp", help="Bind active work package for a project")
    p.add_argument("--project", required=True)
    p.add_argument("--wp", required=True)
    p.set_defaults(func=_cmd_bind_wp)

    p = sub.add_parser("smoke", help="Append fixture rows + render (labeled fixture-smoke)")
    p.add_argument("--project", default="agent-brain")
    p.set_defaults(func=_cmd_smoke)

    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

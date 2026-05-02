"""Library-owned CLI entrypoints for spec-kit script wrappers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentskills.skills.spec_kit.issue_emitter import (
    Approval,
    build_emission,
    load_approval,
    write_audit,
)
from agentskills.skills.spec_kit.plan_builder import RequestType, build_plan


def _build_plan_parser() -> argparse.ArgumentParser:
    """Builds CLI parser for deterministic planning script."""
    parser = argparse.ArgumentParser(
        description=(
            "Builds a deterministic execution plan from a spec-kit skill input payload."
        )
    )
    parser.add_argument("--input", required=True, help="Path to input JSON payload")
    parser.add_argument("--output", required=True, help="Path to output JSON plan")
    parser.add_argument(
        "--request-type",
        choices=[RequestType.NEW_FEATURE.value, RequestType.BEHAVIOR_CHANGE.value],
        help="Override request type in input payload",
    )
    return parser


def run_plan_script(argv: list[str] | None = None) -> int:
    """Runs the deterministic planning script CLI."""
    parser = _build_plan_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if args.request_type:
        payload["request_type"] = args.request_type
    plan = build_plan(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def _build_emit_parser() -> argparse.ArgumentParser:
    """Builds CLI parser for deterministic issue emission."""
    parser = argparse.ArgumentParser(
        description=(
            "Emits deterministic GitHub issue create commands from a plan payload."
        )
    )
    parser.add_argument("--plan", required=True, help="Path to plan JSON")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument("--repo", required=True, help="GitHub repository owner/name")
    parser.add_argument(
        "--allow-repo",
        action="append",
        default=[],
        help="Allowlisted repository owner/name; can be provided multiple times",
    )
    parser.add_argument(
        "--approval",
        help="Path to approval JSON (required when --publish is set)",
    )
    parser.add_argument(
        "--audit-log",
        default=".agents/audit/spec_kit_emit_issues.jsonl",
        help="Path to JSONL audit log file",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish issues via gh CLI (requires explicit approval)",
    )
    return parser


def run_emit_script(argv: list[str] | None = None) -> int:
    """Runs the issue emission workflow CLI."""
    parser = _build_emit_parser()
    args = parser.parse_args(argv)

    try:
        plan_path = Path(args.plan)
        output_path = Path(args.output)

        plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
        approval: Approval | None = None
        if args.approval:
            approval = load_approval(Path(args.approval))

        result = build_emission(
            plan=plan_payload,
            repo=args.repo,
            publish=bool(args.publish),
            approval=approval,
            allow_repos=list(args.allow_repo),
        )
    except (ValueError, PermissionError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1

    write_audit(Path(args.audit_log), result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


def run_spec_kit_cli(argv: list[str] | None = None) -> int:
    """Runs unified spec-kit CLI with explicit plan and emit subcommands."""
    command_argv = list(argv if argv is not None else sys.argv[1:])
    if not command_argv:
        print("usage: python -m agentskills.skills.spec_kit <plan|emit> ...")
        return 1

    command = command_argv[0]
    args = command_argv[1:]
    if command == "plan":
        return run_plan_script(args)
    if command == "emit":
        return run_emit_script(args)

    print(f"unknown spec-kit command: {command}")
    return 1

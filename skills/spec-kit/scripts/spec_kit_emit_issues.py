#!/usr/bin/env python3
"""Emits deterministic GitHub issue create commands from a plan payload."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Approval:
    """Represents human approval state for issue publication."""

    approved: bool
    approver: str
    notes: str


def _build_parser() -> argparse.ArgumentParser:
    """Builds CLI parser for deterministic issue emission."""
    parser = argparse.ArgumentParser(description=__doc__)
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


def _load_approval(path: Path) -> Approval:
    """Loads and validates approval payload from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    approved = bool(payload.get("approved", False))
    approver = str(payload.get("approver", "")).strip()
    notes = str(payload.get("notes", "")).strip()

    if not approver:
        raise ValueError("approval approver must not be empty")

    return Approval(approved=approved, approver=approver, notes=notes)


def _build_command(repo: str, draft: dict[str, object]) -> list[str]:
    """Builds deterministic gh command for a single issue draft."""
    title = str(draft.get("title", "")).strip()
    body = str(draft.get("body", "")).strip()

    if not title:
        raise ValueError("issue draft title must not be empty")

    labels = draft.get("labels", [])
    if not isinstance(labels, list):
        raise ValueError("issue draft labels must be a list")

    blocked_by = draft.get("blocked_by", [])
    if not isinstance(blocked_by, list):
        raise ValueError("issue draft blocked_by must be a list")

    if blocked_by:
        blocked = ", ".join(sorted(str(item) for item in blocked_by))
        body = f"{body}\n\nBlocked by: {blocked}"

    command = [
        "gh",
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]

    clean_labels = sorted(str(item) for item in labels)
    if clean_labels:
        command.extend(["--label", ",".join(clean_labels)])

    return command


def build_emission(
    plan: dict[str, object],
    repo: str,
    publish: bool,
    approval: Approval | None,
    allow_repos: list[str],
) -> dict[str, object]:
    """Builds deterministic issue emission output and optional publish actions."""
    drafts = plan.get("issue_drafts", [])
    if not isinstance(drafts, list):
        raise ValueError("plan issue_drafts must be a list")

    commands: list[str] = []
    created: list[str] = []

    if publish:
        if approval is None:
            raise ValueError("approval is required when --publish is set")
        if not approval.approved:
            raise PermissionError("publication blocked: approval not granted")
        clean_allow_repos = sorted(
            {item.strip() for item in allow_repos if item.strip()}
        )
        if clean_allow_repos and repo not in clean_allow_repos:
            raise PermissionError(
                f"publication blocked: repo '{repo}' is not in allowlist"
            )

    for draft in drafts:
        if not isinstance(draft, dict):
            raise ValueError("each issue draft must be an object")
        command = _build_command(repo, draft)
        commands.append(" ".join(command))

        if publish:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            created.append(completed.stdout.strip())

    return {
        "repo": repo,
        "publish": publish,
        "approval": (
            {
                "approved": approval.approved,
                "approver": approval.approver,
                "notes": approval.notes,
            }
            if approval is not None
            else None
        ),
        "commands": commands,
        "created": created,
        "deterministic": True,
    }


def _write_audit(audit_log: Path, payload: dict[str, object]) -> None:
    """Appends a structured emission audit event to a JSONL file."""
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": "spec_kit_emit_issues",
        "payload": payload,
    }
    with audit_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> int:
    """Runs the issue emission workflow CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        plan_path = Path(args.plan)
        output_path = Path(args.output)

        plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
        approval: Approval | None = None
        if args.approval:
            approval = _load_approval(Path(args.approval))

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

    _write_audit(Path(args.audit_log), result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

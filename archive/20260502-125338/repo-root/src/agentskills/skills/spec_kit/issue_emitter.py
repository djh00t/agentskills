"""Deterministic issue emission utilities for spec-kit workflows."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Approval:
    """Represents human approval state for issue publication."""

    approved: bool
    approver: str
    notes: str


def load_approval(path: Path) -> Approval:
    """Loads and validates approval payload from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    approved = bool(payload.get("approved", False))
    approver = str(payload.get("approver", "")).strip()
    notes = str(payload.get("notes", "")).strip()

    if not approver:
        raise ValueError("approval approver must not be empty")

    return Approval(approved=approved, approver=approver, notes=notes)


def build_issue_command(repo: str, draft: dict[str, object]) -> list[str]:
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
        command = build_issue_command(repo, draft)
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


def write_audit(audit_log: Path, payload: dict[str, object]) -> None:
    """Appends a structured emission audit event to a JSONL file."""
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": "spec_kit_emit_issues",
        "payload": payload,
    }
    with audit_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")

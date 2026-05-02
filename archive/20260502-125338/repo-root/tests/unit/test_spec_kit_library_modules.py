"""Unit tests for centralized spec-kit library modules used by script wrappers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentskills.skills.spec_kit.issue_emitter import (
    Approval,
    build_emission,
    build_issue_command,
    load_approval,
)
from agentskills.skills.spec_kit.plan_builder import build_plan


def test_build_plan_returns_stable_batches_and_labels() -> None:
    """Ensures centralized plan builder preserves deterministic ordering behavior."""
    payload = {
        "spec_title": "Deterministic planning",
        "spec_body": "Validate stable ordering and deterministic output for tasks.",
        "request_type": "behavior-change",
        "tasks": [
            {
                "task_id": "b",
                "title": "Task B",
                "description": "after a",
                "depends_on": ["a"],
                "parallelizable": True,
            },
            {
                "task_id": "a",
                "title": "Task A",
                "description": "first",
                "depends_on": [],
                "parallelizable": True,
            },
        ],
    }

    plan = build_plan(payload)

    assert plan["ordered_task_ids"] == ["a", "b"]
    assert plan["parallel_groups"] == [["a"], ["b"]]
    assert plan["request_type"] == "behavior-change"
    assert "behavior-change" in plan["issue_drafts"][0]["labels"]


def test_build_plan_rejects_unknown_dependencies() -> None:
    """Ensures centralized plan builder enforces dependency integrity."""
    payload = {
        "spec_title": "Invalid planning",
        "spec_body": "Body text",
        "tasks": [
            {
                "task_id": "a",
                "title": "Task A",
                "depends_on": ["missing"],
            }
        ],
    }

    with pytest.raises(ValueError, match="unknown task"):
        build_plan(payload)


def test_build_issue_command_appends_blocked_by_note() -> None:
    """Ensures issue command generation preserves deterministic blocked-by text."""
    command = build_issue_command(
        "djh00t/agentskills",
        {
            "title": "Task A",
            "body": "Implement A",
            "labels": ["spec-kit", "agent-execution"],
            "blocked_by": ["task-z", "task-a"],
        },
    )

    assert command[0:3] == ["gh", "issue", "create"]
    joined = " ".join(command)
    assert "Blocked by: task-a, task-z" in joined


def test_load_approval_requires_approver(tmp_path: Path) -> None:
    """Ensures approval payload loader validates approver field."""
    path = tmp_path / "approval.json"
    path.write_text(json.dumps({"approved": True, "approver": ""}), encoding="utf-8")

    with pytest.raises(ValueError, match="approver"):
        load_approval(path)


def test_build_emission_blocks_publish_without_approval() -> None:
    """Ensures publish mode requires explicit approval in centralized emitter."""
    with pytest.raises(ValueError, match="approval is required"):
        build_emission(
            plan={
                "issue_drafts": [
                    {
                        "title": "Task A",
                        "body": "Implement",
                        "labels": ["spec-kit"],
                        "blocked_by": [],
                    }
                ]
            },
            repo="djh00t/agentskills",
            publish=True,
            approval=None,
            allow_repos=[],
        )


def test_build_emission_enforces_allowlist() -> None:
    """Ensures allowlist protection is enforced for publish mode."""
    with pytest.raises(PermissionError, match="not in allowlist"):
        build_emission(
            plan={
                "issue_drafts": [
                    {
                        "title": "Task A",
                        "body": "Implement",
                        "labels": ["spec-kit"],
                        "blocked_by": [],
                    }
                ]
            },
            repo="djh00t/agentskills",
            publish=True,
            approval=Approval(approved=True, approver="tester", notes="ok"),
            allow_repos=["other/repo"],
        )

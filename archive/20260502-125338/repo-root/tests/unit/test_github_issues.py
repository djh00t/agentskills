"""Unit tests for GitHub issue publishing controls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentskills.contracts.spec_kit_models import IssueDraft
from agentskills.integrations.github_issues import GitHubIssuePublisher


def _draft() -> IssueDraft:
    """Builds a representative issue draft for tests."""
    return IssueDraft(
        title="Task A",
        body="Implement task A",
        labels=["spec-kit"],
        blocked_by=[],
    )


def test_create_issue_dry_run_writes_audit_record(tmp_path: Path) -> None:
    """Ensures dry-run emits command and appends structured audit record."""
    audit_path = tmp_path / "audit.jsonl"
    publisher = GitHubIssuePublisher(
        repo="djh00t/agentskills",
        audit_log_path=audit_path,
    )

    command = publisher.create_issue(_draft(), dry_run=True)

    assert "gh issue create" in command
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "dry_run"
    assert record["repo"] == "djh00t/agentskills"


def test_create_issue_publish_blocked_when_repo_not_allowlisted() -> None:
    """Ensures publication is blocked for non-allowlisted repositories."""
    publisher = GitHubIssuePublisher(
        repo="djh00t/agentskills",
        allowed_repos=("other/repo",),
    )

    with pytest.raises(PermissionError, match="not in allowlist"):
        publisher.create_issue(_draft(), dry_run=False)

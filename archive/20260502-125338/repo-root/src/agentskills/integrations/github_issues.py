"""GitHub issue publication integration using the `gh` CLI."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agentskills.contracts.spec_kit_models import IssueDraft


@dataclass
class GitHubIssuePublisher:
    """Publishes issue drafts to GitHub through the official CLI."""

    repo: str
    allowed_repos: tuple[str, ...] = ()
    audit_log_path: Path | None = None

    def create_issue(self, draft: IssueDraft, dry_run: bool = True) -> str:
        """Creates an issue or returns a deterministic dry-run command."""
        if not dry_run:
            self._assert_publish_allowed()

        labels = ",".join(sorted(draft.labels)) if draft.labels else ""
        body = draft.body
        if draft.blocked_by:
            dependency_note = "\n\nBlocked by: " + ", ".join(sorted(draft.blocked_by))
            body = f"{body}{dependency_note}"

        command = [
            "gh",
            "issue",
            "create",
            "--repo",
            self.repo,
            "--title",
            draft.title,
            "--body",
            body,
        ]
        if labels:
            command.extend(["--label", labels])

        if dry_run:
            self._write_audit(
                event="dry_run",
                title=draft.title,
                command=" ".join(command),
            )
            return " ".join(command)

        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        self._write_audit(
            event="published",
            title=draft.title,
            command=" ".join(command),
            result=completed.stdout.strip(),
        )
        return completed.stdout.strip()

    def _assert_publish_allowed(self) -> None:
        """Ensures target repository is explicitly allowed for publishing."""
        if self.allowed_repos and self.repo not in self.allowed_repos:
            msg = f"publish blocked: repo '{self.repo}' is not in allowlist"
            raise PermissionError(msg)

    def _write_audit(
        self,
        event: str,
        title: str,
        command: str,
        result: str = "",
    ) -> None:
        """Writes structured audit event when audit path is configured."""
        if self.audit_log_path is None:
            return
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "repo": self.repo,
            "title": title,
            "command": command,
            "result": result,
        }
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

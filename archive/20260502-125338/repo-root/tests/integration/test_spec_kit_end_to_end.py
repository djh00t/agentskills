"""Integration tests for end-to-end orchestrator behavior."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from agentskills.contracts.spec_kit_models import (
    ApprovalDecision,
    SpecSubmission,
    TaskSpec,
)
from agentskills.integrations.github_issues import GitHubIssuePublisher
from agentskills.skills.spec_kit.orchestrator import WorkflowOrchestrator


@dataclass
class StaticHumanGate:
    """Human gate test double with deterministic behavior."""

    approved: bool

    def ask(self, question: object) -> str:
        """Returns deterministic response for clarifications."""
        return f"clarified:{question}"

    def approve(self, summary: str) -> ApprovalDecision:
        """Returns fixed approval decision."""
        return ApprovalDecision(
            approved=self.approved,
            approver="integration",
            notes=summary,
        )


@dataclass
class StaticRunner:
    """Upstream runner test double for integration tests."""

    last_spec_file: Path | None = None
    last_specs_dir: Path | None = None
    mutate_task_labels: bool = False

    def run_upstream_help_checks(self) -> None:
        """No-op upstream check for deterministic tests."""

    def taskstoissues_template_ref(self) -> str:
        """Returns stable template reference for test assertions."""
        return "templates/commands/taskstoissues.md"

    def initialize_project(self, project_dir: Path, ai_assistant: str) -> None:
        """No-op project initialization for tests."""

    def create_feature(
        self,
        project_dir: Path,
        feature_description: str,
        short_name: str | None = None,
    ) -> dict[str, str]:
        """Returns deterministic feature metadata for tests."""
        feature_dir = Path(tempfile.mkdtemp(prefix="spec-kit-feature-"))
        spec_file = feature_dir / "spec.md"
        spec_file.write_text("# Spec\n", encoding="utf-8")
        self.last_spec_file = spec_file
        return {
            "BRANCH_NAME": short_name or "001-spec",
            "SPEC_FILE": str(spec_file),
            "FEATURE_NUM": "001",
        }

    def check_prerequisites(
        self,
        project_dir: Path,
        feature_name: str,
        paths_only: bool = False,
        include_tasks: bool = False,
        require_tasks: bool = False,
    ) -> dict[str, str]:
        """Returns deterministic prerequisite metadata for tests."""
        if self.mutate_task_labels and include_tasks and require_tasks:
            if self.last_specs_dir is None:
                msg = "missing specs dir for task mutation"
                raise AssertionError(msg)
            tasks_file = self.last_specs_dir / "tasks.md"
            tasks_file.write_text(
                "\n".join(
                    [
                        "# Tasks",
                        "",
                        "## Phase 1",
                        "- [x] 1 Execute task-1",
                        "",
                        "## Phase 2",
                        "- [ ] task-two Execute task-2",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        return {"FEATURE_DIR": feature_name}

    def setup_plan(self, project_dir: Path, feature_name: str) -> dict[str, str]:
        """Returns deterministic plan paths for tests."""
        specs_dir = Path(tempfile.mkdtemp(prefix="spec-kit-plan-"))
        self.last_specs_dir = specs_dir
        return {
            "FEATURE_SPEC": str(specs_dir / "spec.md"),
            "IMPL_PLAN": str(specs_dir / "plan.md"),
            "SPECS_DIR": str(specs_dir),
            "BRANCH": feature_name,
            "HAS_GIT": "true",
        }

    def update_agent_context(
        self,
        project_dir: Path,
        feature_name: str,
        agent_name: str,
    ) -> None:
        """No-op agent context update for tests."""


def _build_submission() -> SpecSubmission:
    """Builds a valid submission for integration tests."""
    return SpecSubmission(
        spec_title="Spec",
        spec_body=("This specification body is long enough for validation to pass."),
        tasks=[
            TaskSpec(
                task_id="task-1",
                title="Task 1",
                description="Do task 1",
            ),
            TaskSpec(
                task_id="task-2",
                title="Task 2",
                description="Do task 2",
                depends_on=["task-1"],
            ),
        ],
    )


def test_orchestrator_returns_plan_when_approved() -> None:
    """Checks approved runs produce deterministic plan and drafts."""
    orchestrator = WorkflowOrchestrator(
        human_gate=StaticHumanGate(approved=True),
        issue_publisher=GitHubIssuePublisher(repo="djh00t/agentskills"),
        runner=StaticRunner(),
    )

    plan = orchestrator.run(_build_submission(), dry_run=True)

    assert plan.ordered_task_ids == ["task-1", "task-2"]
    assert plan.parallel_groups == [["task-1"], ["task-2"]]
    assert len(plan.issue_drafts) == 2
    assert "Upstream template" in plan.issue_drafts[0].body


def test_orchestrator_writes_expected_spec_and_tasks_artifacts() -> None:
    """Checks exact deterministic contents of generated spec and tasks artifacts."""
    runner = StaticRunner()
    orchestrator = WorkflowOrchestrator(
        human_gate=StaticHumanGate(approved=True),
        issue_publisher=GitHubIssuePublisher(repo="djh00t/agentskills"),
        runner=runner,
    )

    orchestrator.run(_build_submission(), dry_run=True)

    if runner.last_spec_file is None or runner.last_specs_dir is None:
        msg = "runner did not capture output paths"
        raise AssertionError(msg)

    spec_content = runner.last_spec_file.read_text(encoding="utf-8")
    assert spec_content == (
        "# Spec\n"
        "\n"
        "Request Type: new-feature\n"
        "\n"
        "## Summary\n"
        "This specification body is long enough for validation to pass.\n"
    )

    tasks_content = (runner.last_specs_dir / "tasks.md").read_text(encoding="utf-8")
    assert tasks_content == (
        "# Tasks\n"
        "\n"
        "## Phase 1\n"
        "- [ ] T001 [US1] Execute task-1\n"
        "\n"
        "## Phase 2\n"
        "- [ ] T002 [US1] Execute task-2\n"
    )

    assert (runner.last_specs_dir / "research.md").is_file()
    assert (runner.last_specs_dir / "data-model.md").is_file()
    assert (runner.last_specs_dir / "quickstart.md").is_file()
    assert (runner.last_specs_dir / "contracts" / "issue-draft-contract.md").is_file()

    analysis_content = (runner.last_specs_dir / "analysis.md").read_text(
        encoding="utf-8"
    )
    assert "Status: No fixes required" in analysis_content


def test_orchestrator_appends_clarifications_for_short_spec_body() -> None:
    """Checks short spec bodies trigger deterministic clarification block append."""
    runner = StaticRunner()
    orchestrator = WorkflowOrchestrator(
        human_gate=StaticHumanGate(approved=True),
        issue_publisher=GitHubIssuePublisher(repo="djh00t/agentskills"),
        runner=runner,
    )
    submission = SpecSubmission(
        spec_title="Spec",
        spec_body="too short",
        tasks=[
            TaskSpec(task_id="task-1", title="Task 1", description="Do task 1"),
            TaskSpec(
                task_id="task-2",
                title="Task 2",
                description="Do task 2",
                depends_on=["task-1"],
            ),
        ],
    )

    orchestrator.run(submission, dry_run=True)

    if runner.last_spec_file is None:
        msg = "runner did not capture spec path"
        raise AssertionError(msg)

    spec_content = runner.last_spec_file.read_text(encoding="utf-8")
    assert "## Clarifications\n" in spec_content
    assert "- Please provide more detail in the specification body.\n" in spec_content
    assert "- Answer: clarified:ClarificationQuestion(" in spec_content


def test_orchestrator_bootstraps_tasks_when_missing() -> None:
    """Checks deterministic baseline task generation when no tasks are provided."""
    runner = StaticRunner()
    orchestrator = WorkflowOrchestrator(
        human_gate=StaticHumanGate(approved=True),
        issue_publisher=GitHubIssuePublisher(repo="djh00t/agentskills"),
        runner=runner,
    )
    submission = SpecSubmission(
        spec_title="Spec",
        spec_body="This specification body is long enough for validation to pass.",
        tasks=[],
    )

    plan = orchestrator.run(submission, dry_run=True)

    assert plan.ordered_task_ids == [
        "capture-requirements",
        "design-artifacts",
        "implementation-plan",
    ]


def test_orchestrator_normalizes_malformed_tasks_labels() -> None:
    """Checks analyze auto-fix normalizes malformed tasks labels."""
    runner = StaticRunner(mutate_task_labels=True)
    orchestrator = WorkflowOrchestrator(
        human_gate=StaticHumanGate(approved=True),
        issue_publisher=GitHubIssuePublisher(repo="djh00t/agentskills"),
        runner=runner,
    )

    orchestrator.run(_build_submission(), dry_run=True)

    if runner.last_specs_dir is None:
        msg = "runner did not capture specs dir"
        raise AssertionError(msg)

    tasks_content = (runner.last_specs_dir / "tasks.md").read_text(encoding="utf-8")
    assert "- [ ] T001 [US1] Execute task-1\n" in tasks_content
    assert "- [ ] T002 [US1] Execute task-2\n" in tasks_content

    analysis_content = (runner.last_specs_dir / "analysis.md").read_text(
        encoding="utf-8"
    )
    assert "Normalized tasks.md labels to checklist format" in analysis_content


def test_orchestrator_raises_when_not_approved() -> None:
    """Checks rejected approval blocks publication."""
    orchestrator = WorkflowOrchestrator(
        human_gate=StaticHumanGate(approved=False),
        issue_publisher=GitHubIssuePublisher(repo="djh00t/agentskills"),
        runner=StaticRunner(),
    )

    with pytest.raises(PermissionError, match="not approved"):
        orchestrator.run(_build_submission(), dry_run=True)

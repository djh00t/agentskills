"""BDD step definitions for spec-kit workflow scenarios."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from agentskills.contracts.spec_kit_models import (
    ApprovalDecision,
    ExecutionPlan,
    SpecSubmission,
    TaskSpec,
)
from agentskills.integrations.github_issues import GitHubIssuePublisher
from agentskills.skills.spec_kit.orchestrator import WorkflowOrchestrator


@dataclass
class StubHumanGate:
    """Stub human gate for deterministic test behavior."""

    approve_value: bool

    def ask(self, question: object) -> str:
        """Returns deterministic clarification answer."""
        return f"answered:{question}"

    def approve(self, summary: str) -> ApprovalDecision:
        """Returns fixed approval decision for scenario."""
        return ApprovalDecision(
            approved=self.approve_value,
            approver="test-user",
            notes=summary,
        )


@dataclass
class StubRunner:
    """Stub upstream runner for deterministic workflow tests."""

    def run_upstream_help_checks(self) -> None:
        """No-op upstream checks for tests."""

    def taskstoissues_template_ref(self) -> str:
        """Returns stable template reference for tests."""
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
        return {
            "BRANCH_NAME": short_name or "001-sample",
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
        return {"FEATURE_DIR": feature_name}

    def setup_plan(self, project_dir: Path, feature_name: str) -> dict[str, str]:
        """Returns deterministic plan paths for tests."""
        specs_dir = Path(tempfile.mkdtemp(prefix="spec-kit-plan-"))
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


@dataclass
class ScenarioContext:
    """Holds mutable state across BDD steps."""

    submission: SpecSubmission | None = None
    plan: ExecutionPlan | None = None
    error: Exception | None = None


@scenario(
    "spec_kit_workflow.feature",
    "Build deterministic plan and publish in dry-run mode",
)
def test_plan_and_publish_dry_run() -> None:
    """Executes happy-path deterministic workflow scenario."""


@scenario(
    "spec_kit_workflow.feature",
    "Deny publication when approval is rejected",
)
def test_reject_publication() -> None:
    """Executes rejection scenario."""


@pytest.fixture
def scenario_context() -> ScenarioContext:
    """Provides mutable scenario context."""
    return ScenarioContext()


@given("a valid spec submission with dependencies")
def given_valid_submission(scenario_context: ScenarioContext) -> None:
    """Creates submission fixture with deterministic task graph."""
    scenario_context.submission = SpecSubmission(
        spec_title="Sample",
        spec_body="This specification contains enough words for validation.",
        tasks=[
            TaskSpec(task_id="a", title="A", depends_on=[]),
            TaskSpec(task_id="b", title="B", depends_on=["a"]),
            TaskSpec(task_id="c", title="C", depends_on=["a"]),
        ],
    )


@when(parsers.parse("the workflow runs with approval {state}"))
def when_workflow_runs(state: str, scenario_context: ScenarioContext) -> None:
    """Runs orchestrator with configured approval behavior."""
    approve = state == "granted"
    gate = StubHumanGate(approve_value=approve)
    orchestrator = WorkflowOrchestrator(
        human_gate=gate,
        issue_publisher=GitHubIssuePublisher(repo="djh00t/agentskills"),
        runner=StubRunner(),
    )
    if scenario_context.submission is None:
        msg = "submission was not initialized"
        raise AssertionError(msg)

    try:
        scenario_context.plan = orchestrator.run(
            scenario_context.submission,
            dry_run=True,
        )
        scenario_context.error = None
    except PermissionError as error:
        scenario_context.plan = None
        scenario_context.error = error


@then("execution order is deterministic")
def then_order_is_deterministic(scenario_context: ScenarioContext) -> None:
    """Validates stable task ordering in plan."""
    plan = scenario_context.plan
    assert plan is not None
    assert plan.ordered_task_ids == ["a", "b", "c"]


@then("parallel groups are produced")
def then_parallel_groups_exist(scenario_context: ScenarioContext) -> None:
    """Validates deterministic parallel grouping."""
    plan = scenario_context.plan
    assert plan is not None
    assert plan.parallel_groups == [["a"], ["b", "c"]]


@then("issue drafts are generated")
def then_issue_drafts_exist(scenario_context: ScenarioContext) -> None:
    """Validates issue drafts are present for planned tasks."""
    plan = scenario_context.plan
    assert plan is not None
    assert len(plan.issue_drafts) == 3


@then("publication is blocked")
def then_publication_blocked(scenario_context: ScenarioContext) -> None:
    """Validates rejection prevents publication."""
    error = scenario_context.error
    assert isinstance(error, PermissionError)

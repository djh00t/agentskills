"""Deterministic orchestrator for spec-kit skill execution."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from agentskills.contracts.spec_kit_models import (
    ClarificationQuestion,
    ExecutionPlan,
    IssueDraft,
    SpecSubmission,
    TaskSpec,
    validate_submission,
)
from agentskills.integrations.github_issues import GitHubIssuePublisher
from agentskills.planning.dependency_graph import build_execution_batches
from agentskills.skills.spec_kit.human_gate import HumanGate
from agentskills.skills.spec_kit.runner import SpecKitRunner


def _default_runner() -> SpecKitRunner:
    """Builds default runner for upstream specify CLI."""
    return SpecKitRunner()


@dataclass
class WorkflowOrchestrator:
    """Coordinates validation, planning, human gates, and issue publication."""

    human_gate: HumanGate
    issue_publisher: GitHubIssuePublisher
    runner: SpecKitRunner = field(default_factory=_default_runner)

    def run(
        self,
        submission: SpecSubmission,
        dry_run: bool = True,
    ) -> ExecutionPlan:
        """Executes deterministic orchestration with human checkpoints."""
        validate_submission(submission)
        self.runner.run_upstream_help_checks()

        project_dir = Path(submission.project_dir).resolve()
        self.runner.initialize_project(project_dir, submission.ai_assistant)

        feature_meta = self.runner.create_feature(
            project_dir=project_dir,
            feature_description=submission.spec_title,
            short_name=self._short_name(submission.spec_title, submission.request_type),
        )
        feature_name = feature_meta["BRANCH_NAME"]
        spec_file = Path(feature_meta["SPEC_FILE"])

        self._write_spec(spec_file, submission)
        self.runner.check_prerequisites(
            project_dir=project_dir,
            feature_name=feature_name,
            paths_only=True,
        )

        upstream_template = self.runner.taskstoissues_template_ref()
        self._run_clarification_gate(submission, spec_file)
        self._resolve_spec_placeholders(spec_file)
        plan_paths = self.runner.setup_plan(
            project_dir=project_dir,
            feature_name=feature_name,
        )
        self.runner.update_agent_context(
            project_dir=project_dir,
            feature_name=feature_name,
            agent_name=submission.ai_assistant,
        )

        specs_dir = Path(plan_paths["SPECS_DIR"])
        self._write_design_artifacts(specs_dir, submission)
        plan = self._build_plan(submission, upstream_template)

        tasks_file = specs_dir / "tasks.md"
        self._write_tasks(tasks_file, plan)
        self.runner.check_prerequisites(
            project_dir=project_dir,
            feature_name=feature_name,
            include_tasks=True,
            require_tasks=True,
        )
        self._run_analysis_and_fix(spec_file, tasks_file, plan, specs_dir)

        summary = (
            f"{len(plan.issue_drafts)} issue draft(s), dry_run={dry_run}, "
            f"template={upstream_template}"
        )
        decision = self.human_gate.approve(summary)
        if not decision.approved:
            msg = "publication was not approved"
            raise PermissionError(msg)

        for draft in plan.issue_drafts:
            self.issue_publisher.create_issue(draft, dry_run=dry_run)

        return plan

    def _run_clarification_gate(
        self,
        submission: SpecSubmission,
        spec_file: Path,
    ) -> None:
        """Asks deterministic clarifying questions for weak inputs."""
        if len(submission.spec_body.strip().split()) < 5:
            question = ClarificationQuestion(
                question_id="spec_body_min_context",
                prompt="Please provide more detail in the specification body.",
            )
            answer = self.human_gate.ask(question)
            with spec_file.open("a", encoding="utf-8") as handle:
                handle.write("\n\n## Clarifications\n")
                handle.write(f"- {question.prompt}\n")
                handle.write(f"- Answer: {answer}\n")

    def _build_plan(
        self,
        submission: SpecSubmission,
        upstream_template: str,
    ) -> ExecutionPlan:
        """Builds deterministic execution plan and issue drafts."""
        tasks = submission.tasks or self._bootstrap_tasks(submission)
        batches = build_execution_batches(tasks)
        ordered_task_ids = [task_id for batch in batches for task_id in batch]

        task_by_id = {task.task_id: task for task in tasks}
        issue_drafts: list[IssueDraft] = []
        for task_id in ordered_task_ids:
            task = task_by_id[task_id]
            issue_drafts.append(
                IssueDraft(
                    title=task.title,
                    body=(
                        (
                            task.description
                            or f"Generated from spec: {submission.spec_title}"
                        )
                        + f"\n\nUpstream template: {upstream_template}"
                    ),
                    labels=["spec-kit", "agent-execution", submission.request_type],
                    blocked_by=sorted(task.depends_on),
                )
            )

        return ExecutionPlan(
            ordered_task_ids=ordered_task_ids,
            parallel_groups=batches,
            issue_drafts=issue_drafts,
        )

    def _bootstrap_tasks(self, submission: SpecSubmission) -> list[TaskSpec]:
        """Builds deterministic baseline tasks when explicit tasks are absent."""
        return [
            TaskSpec(
                task_id="capture-requirements",
                title="Capture detailed requirements",
                description=(
                    "Expand specification details and acceptance criteria for "
                    f"{submission.spec_title}."
                ),
            ),
            TaskSpec(
                task_id="design-artifacts",
                title="Produce design artifacts",
                description=(
                    "Generate plan, research, data model, and contracts for "
                    f"{submission.spec_title}."
                ),
                depends_on=["capture-requirements"],
            ),
            TaskSpec(
                task_id="implementation-plan",
                title="Prepare implementation execution",
                description=(
                    "Create dependency-ordered tasks and delivery checkpoints "
                    f"for {submission.spec_title}."
                ),
                depends_on=["design-artifacts"],
                parallelizable=False,
            ),
        ]

    def _write_spec(self, spec_file: Path, submission: SpecSubmission) -> None:
        """Writes deterministic spec content into upstream-created spec file."""
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(
            "\n".join(
                [
                    f"# {submission.spec_title}",
                    "",
                    f"Request Type: {submission.request_type}",
                    "",
                    "## Summary",
                    submission.spec_body,
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_tasks(self, tasks_file: Path, plan: ExecutionPlan) -> None:
        """Writes deterministic tasks.md from computed execution plan."""
        lines: list[str] = ["# Tasks", ""]
        step_number = 1
        for group_index, group in enumerate(plan.parallel_groups, start=1):
            lines.append(f"## Phase {group_index}")
            for task_id in group:
                lines.append(f"- [ ] T{step_number:03d} [US1] Execute {task_id}")
                step_number += 1
            lines.append("")
        tasks_file.write_text("\n".join(lines), encoding="utf-8")

    def _resolve_spec_placeholders(self, spec_file: Path) -> None:
        """Resolves upstream clarification placeholders with deterministic answers."""
        content = spec_file.read_text(encoding="utf-8")
        pattern = re.compile(r"\[NEEDS CLARIFICATION:([^\]]+)\]")

        def _replace(match: re.Match[str]) -> str:
            prompt = match.group(1).strip()
            stable_id = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
            question = ClarificationQuestion(
                question_id=f"clarify-{stable_id}",
                prompt=prompt,
            )
            answer = self.human_gate.ask(question).strip()
            if not answer:
                return "Clarification: defaulted for planning"
            return f"Clarification: {answer}"

        updated = pattern.sub(_replace, content)
        if updated != content:
            spec_file.write_text(updated, encoding="utf-8")

    def _write_design_artifacts(
        self,
        specs_dir: Path,
        submission: SpecSubmission,
    ) -> None:
        """Writes deterministic design artifacts aligned with upstream plan stage."""
        specs_dir.mkdir(parents=True, exist_ok=True)

        (specs_dir / "research.md").write_text(
            "\n".join(
                [
                    "# Research",
                    "",
                    (
                        "- Decision: Use deterministic orchestration for "
                        f"{submission.spec_title}"
                    ),
                    "- Rationale: Predictable outputs and repeatable workflows",
                    "- Alternatives considered: Fully interactive manual planning",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        (specs_dir / "data-model.md").write_text(
            "\n".join(
                [
                    "# Data Model",
                    "",
                    "## Entities",
                    "- Specification: title, body, request_type",
                    "- Task: task_id, title, depends_on, parallelizable",
                    "- IssueDraft: title, body, labels, blocked_by",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        contracts_dir = specs_dir / "contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        (contracts_dir / "issue-draft-contract.md").write_text(
            "\n".join(
                [
                    "# Issue Draft Contract",
                    "",
                    "Required fields:",
                    "- title (string, non-empty)",
                    "- body (string)",
                    "- labels (string array)",
                    "- blocked_by (string array)",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        (specs_dir / "quickstart.md").write_text(
            "\n".join(
                [
                    "# Quickstart",
                    "",
                    "1. Run deterministic orchestration with input specification.",
                    "2. Review generated tasks and analysis outputs.",
                    "3. Approve issue publication when drafts are acceptable.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def _run_analysis_and_fix(
        self,
        spec_file: Path,
        tasks_file: Path,
        plan: ExecutionPlan,
        specs_dir: Path,
    ) -> None:
        """Analyzes artifacts and applies deterministic auto-fixes."""
        fixes: list[str] = []

        spec_content = spec_file.read_text(encoding="utf-8")
        if "## Summary" not in spec_content:
            spec_file.write_text(
                spec_content + "\n## Summary\nAuto-fixed summary.\n",
                encoding="utf-8",
            )
            fixes.append("Added missing spec summary section")

        normalized = self._normalize_task_labels(tasks_file, plan)
        if normalized:
            fixes.append("Normalized tasks.md labels to checklist format")

        expected_task_lines = [
            f"- [ ] T{index:03d} [US1] Execute {task_id}"
            for index, task_id in enumerate(plan.ordered_task_ids, start=1)
        ]
        tasks_content = tasks_file.read_text(encoding="utf-8")
        for line in expected_task_lines:
            if line not in tasks_content:
                self._write_tasks(tasks_file, plan)
                fixes.append("Rewrote tasks.md to restore deterministic ordering")
                break

        status = "No fixes required" if not fixes else "Applied fixes"
        report_lines = ["# Analyze Report", "", f"Status: {status}", "", "## Findings"]
        if fixes:
            for fix in fixes:
                report_lines.append(f"- {fix}")
        else:
            report_lines.append(
                "- Artifacts are consistent with deterministic workflow"
            )

        (specs_dir / "analysis.md").write_text(
            "\n".join(report_lines) + "\n",
            encoding="utf-8",
        )

    def _normalize_task_labels(self, tasks_file: Path, plan: ExecutionPlan) -> bool:
        """Normalizes task checklist labels to deterministic upstream-style format."""
        lines = tasks_file.read_text(encoding="utf-8").splitlines()
        updated = list(lines)
        changed = False

        for index, task_id in enumerate(plan.ordered_task_ids, start=1):
            canonical = f"- [ ] T{index:03d} [US1] Execute {task_id}"
            for line_index, line in enumerate(updated):
                if f"Execute {task_id}" not in line:
                    continue
                if line != canonical:
                    updated[line_index] = canonical
                    changed = True
                break

        if changed:
            tasks_file.write_text("\n".join(updated) + "\n", encoding="utf-8")
        return changed

    def _short_name(self, spec_title: str, request_type: str) -> str:
        """Builds deterministic short name for upstream feature creation."""
        seed = "behavior-change" if request_type == "behavior-change" else "new-feature"
        title_token = "-".join(spec_title.lower().split()[:2]) or "spec"
        return f"{seed}-{title_token}"[:40]

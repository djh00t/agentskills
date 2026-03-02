"""Typed models for deterministic Spec-Kit orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TaskSpec:
    """Defines a single task and its dependency metadata."""

    task_id: str
    title: str
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    parallelizable: bool = True


@dataclass(frozen=True)
class IssueDraft:
    """Defines a GitHub issue draft derived from planned work."""

    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpecSubmission:
    """Defines input payload for a Spec-Kit skill run."""

    spec_title: str
    spec_body: str
    request_type: str = "new-feature"
    project_dir: str = "."
    ai_assistant: str = "codex"
    tasks: list[TaskSpec] = field(default_factory=list)


@dataclass(frozen=True)
class ApprovalDecision:
    """Defines human approval result for publication actions."""

    approved: bool
    approver: str
    notes: str = ""


@dataclass(frozen=True)
class ClarificationQuestion:
    """Defines a clarification prompt required before planning."""

    question_id: str
    prompt: str


@dataclass(frozen=True)
class ExecutionPlan:
    """Defines deterministic ordering and grouping of executable tasks."""

    ordered_task_ids: list[str]
    parallel_groups: list[list[str]]
    issue_drafts: list[IssueDraft]


def validate_submission(submission: SpecSubmission) -> None:
    """Validates integrity of a submission and raises on invalid state."""
    if not submission.spec_title.strip():
        msg = "spec_title must not be empty"
        raise ValueError(msg)
    if not submission.spec_body.strip():
        msg = "spec_body must not be empty"
        raise ValueError(msg)
    if submission.request_type not in {"new-feature", "behavior-change"}:
        msg = "request_type must be one of: new-feature, behavior-change"
        raise ValueError(msg)
    if not submission.project_dir.strip():
        msg = "project_dir must not be empty"
        raise ValueError(msg)
    if not submission.ai_assistant.strip():
        msg = "ai_assistant must not be empty"
        raise ValueError(msg)

    task_ids = [task.task_id for task in submission.tasks]
    if len(task_ids) != len(set(task_ids)):
        msg = "task_id values must be unique"
        raise ValueError(msg)

    known_ids = set(task_ids)
    for task in submission.tasks:
        for dependency in task.depends_on:
            if dependency not in known_ids:
                msg = f"task '{task.task_id}' depends on unknown task '{dependency}'"
                raise ValueError(msg)

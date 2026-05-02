"""Deterministic plan builder for spec-kit workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agentskills.contracts.spec_kit_models import TaskSpec
from agentskills.planning.dependency_graph import build_execution_batches


class RequestType(StrEnum):
    """Enumerates supported specification request categories."""

    NEW_FEATURE = "new-feature"
    BEHAVIOR_CHANGE = "behavior-change"


@dataclass(frozen=True)
class PlannerTask:
    """Defines task payload used by script-level planning outputs."""

    task_id: str
    title: str
    description: str
    depends_on: list[str]
    parallelizable: bool


def parse_planner_tasks(raw_tasks: list[dict[str, object]]) -> list[PlannerTask]:
    """Parses task dictionaries and validates required fields."""
    tasks: list[PlannerTask] = []
    seen_ids: set[str] = set()

    for item in raw_tasks:
        task_id = str(item.get("task_id", "")).strip()
        title = str(item.get("title", "")).strip()
        description = str(item.get("description", "")).strip()
        depends_on = [str(dep).strip() for dep in item.get("depends_on", [])]
        parallelizable = bool(item.get("parallelizable", True))

        if not task_id:
            raise ValueError("task_id must not be empty")
        if task_id in seen_ids:
            raise ValueError(f"duplicate task_id: {task_id}")
        if not title:
            raise ValueError(f"task '{task_id}' title must not be empty")

        seen_ids.add(task_id)
        tasks.append(
            PlannerTask(
                task_id=task_id,
                title=title,
                description=description,
                depends_on=depends_on,
                parallelizable=parallelizable,
            )
        )

    known = {task.task_id for task in tasks}
    for task in tasks:
        for dependency in task.depends_on:
            if dependency not in known:
                raise ValueError(
                    f"task '{task.task_id}' depends on unknown task '{dependency}'"
                )

    return tasks


def _to_contract_tasks(tasks: list[PlannerTask]) -> list[TaskSpec]:
    """Converts planner task payloads to core task contracts."""
    return [
        TaskSpec(
            task_id=task.task_id,
            title=task.title,
            description=task.description,
            depends_on=task.depends_on,
            parallelizable=task.parallelizable,
        )
        for task in tasks
    ]


def _issue_drafts(
    spec_title: str,
    request_type: RequestType,
    tasks: list[PlannerTask],
    ordered_task_ids: list[str],
) -> list[dict[str, object]]:
    """Builds deterministic issue drafts in ordered task sequence."""
    task_index = {task.task_id: task for task in tasks}
    drafts: list[dict[str, object]] = []

    for task_id in ordered_task_ids:
        task = task_index[task_id]
        body = task.description or f"Generated from spec: {spec_title}"
        drafts.append(
            {
                "task_id": task.task_id,
                "title": task.title,
                "body": body,
                "labels": ["agent-execution", "spec-kit", request_type.value],
                "blocked_by": sorted(task.depends_on),
            }
        )

    return drafts


def build_plan(payload: dict[str, object]) -> dict[str, object]:
    """Builds deterministic plan output from a skill input payload."""
    spec_title = str(payload.get("spec_title", "")).strip()
    spec_body = str(payload.get("spec_body", "")).strip()
    request_type_value = str(payload.get("request_type", RequestType.NEW_FEATURE))
    raw_tasks = payload.get("tasks", [])

    if not spec_title:
        raise ValueError("spec_title must not be empty")
    if not spec_body:
        raise ValueError("spec_body must not be empty")
    try:
        request_type = RequestType(request_type_value)
    except ValueError as error:
        msg = (
            "request_type must be one of: "
            f"{RequestType.NEW_FEATURE.value}, {RequestType.BEHAVIOR_CHANGE.value}"
        )
        raise ValueError(msg) from error
    if not isinstance(raw_tasks, list):
        raise ValueError("tasks must be a list")

    tasks = parse_planner_tasks(raw_tasks)
    batches = build_execution_batches(_to_contract_tasks(tasks))
    ordered = [task_id for batch in batches for task_id in batch]

    return {
        "spec_title": spec_title,
        "request_type": request_type.value,
        "ordered_task_ids": ordered,
        "parallel_groups": batches,
        "issue_drafts": _issue_drafts(spec_title, request_type, tasks, ordered),
        "deterministic": True,
    }

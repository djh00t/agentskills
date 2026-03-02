#!/usr/bin/env python3
"""Builds a deterministic execution plan from a spec-kit skill input payload."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class RequestType(StrEnum):
    """Enumerates supported specification request categories."""

    NEW_FEATURE = "new-feature"
    BEHAVIOR_CHANGE = "behavior-change"


@dataclass(frozen=True)
class Task:
    """Defines a task used for deterministic planning."""

    task_id: str
    title: str
    description: str
    depends_on: list[str]
    parallelizable: bool


def _parse_tasks(raw_tasks: list[dict[str, object]]) -> list[Task]:
    """Parses task dictionaries and validates required fields."""
    tasks: list[Task] = []
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
            Task(
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


def _build_batches(tasks: list[Task]) -> list[list[str]]:
    """Builds deterministic topological batches for the provided tasks."""
    dependencies: dict[str, set[str]] = {}
    dependents: dict[str, set[str]] = defaultdict(set)

    for task in sorted(tasks, key=lambda item: item.task_id):
        dependencies[task.task_id] = set(task.depends_on)
        for dep in task.depends_on:
            dependents[dep].add(task.task_id)

    remaining = {task.task_id for task in tasks}
    batches: list[list[str]] = []

    while remaining:
        ready = sorted(task_id for task_id in remaining if not dependencies[task_id])
        if not ready:
            raise ValueError("cycle detected in task dependency graph")

        batches.append(ready)
        for task_id in ready:
            remaining.remove(task_id)
            for dependent in sorted(dependents[task_id]):
                dependencies[dependent].discard(task_id)

    return batches


def _issue_drafts(
    spec_title: str,
    request_type: RequestType,
    tasks: list[Task],
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

    tasks = _parse_tasks(raw_tasks)
    batches = _build_batches(tasks)
    ordered = [task_id for batch in batches for task_id in batch]

    return {
        "spec_title": spec_title,
        "request_type": request_type.value,
        "ordered_task_ids": ordered,
        "parallel_groups": batches,
        "issue_drafts": _issue_drafts(spec_title, request_type, tasks, ordered),
        "deterministic": True,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Builds CLI parser for deterministic planning script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to input JSON payload")
    parser.add_argument("--output", required=True, help="Path to output JSON plan")
    parser.add_argument(
        "--request-type",
        choices=[RequestType.NEW_FEATURE.value, RequestType.BEHAVIOR_CHANGE.value],
        help="Override request type in input payload",
    )
    return parser


def main() -> int:
    """Runs the deterministic planning script CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if args.request_type:
        payload["request_type"] = args.request_type
    plan = build_plan(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Dependency planning utilities for deterministic task execution."""

from __future__ import annotations

from collections import defaultdict

from agentskills.contracts.spec_kit_models import TaskSpec


def build_execution_batches(tasks: list[TaskSpec]) -> list[list[str]]:
    """Builds deterministic execution batches from task dependencies.

    Each batch contains tasks that can run in parallel. Batches are ordered
    sequentially by dependency constraints.
    """
    dependencies: dict[str, set[str]] = {}
    dependents: dict[str, set[str]] = defaultdict(set)

    for task in sorted(tasks, key=lambda item: item.task_id):
        dependencies[task.task_id] = set(task.depends_on)
        for dependency in task.depends_on:
            dependents[dependency].add(task.task_id)

    remaining = {task.task_id for task in tasks}
    batches: list[list[str]] = []

    while remaining:
        ready = sorted(task_id for task_id in remaining if not dependencies[task_id])
        if not ready:
            msg = "cycle detected in dependency graph"
            raise ValueError(msg)

        batches.append(ready)
        for task_id in ready:
            remaining.remove(task_id)
            for dependent in sorted(dependents[task_id]):
                dependencies[dependent].discard(task_id)

    return batches

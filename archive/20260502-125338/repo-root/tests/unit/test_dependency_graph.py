"""Unit tests for dependency graph planning logic."""

from __future__ import annotations

import pytest

from agentskills.contracts.spec_kit_models import TaskSpec
from agentskills.planning.dependency_graph import build_execution_batches


def test_build_execution_batches_orders_and_batches_deterministically() -> None:
    """Ensures stable topological ordering and dependency-level grouping."""
    tasks = [
        TaskSpec(task_id="b", title="B", depends_on=["a"]),
        TaskSpec(task_id="a", title="A", depends_on=[]),
        TaskSpec(task_id="c", title="C", depends_on=["a"]),
    ]

    assert build_execution_batches(tasks) == [["a"], ["b", "c"]]


def test_build_execution_batches_raises_on_cycle() -> None:
    """Ensures cycles are rejected."""
    tasks = [
        TaskSpec(task_id="a", title="A", depends_on=["b"]),
        TaskSpec(task_id="b", title="B", depends_on=["a"]),
    ]

    with pytest.raises(ValueError, match="cycle"):
        build_execution_batches(tasks)

"""Unit tests for spec-kit contract models."""

from __future__ import annotations

import pytest

from agentskills.contracts.spec_kit_models import (
    SpecSubmission,
    TaskSpec,
    validate_submission,
)


def test_validate_submission_accepts_valid_payload() -> None:
    """Validates that a correct submission passes checks."""
    submission = SpecSubmission(
        spec_title="Title",
        spec_body="This body includes enough words for validation checks.",
        tasks=[
            TaskSpec(task_id="a", title="Task A", depends_on=[]),
            TaskSpec(task_id="b", title="Task B", depends_on=["a"]),
        ],
    )

    validate_submission(submission)


def test_validate_submission_rejects_duplicate_task_ids() -> None:
    """Validates duplicate IDs raise a value error."""
    submission = SpecSubmission(
        spec_title="Title",
        spec_body="This body includes enough words for validation checks.",
        tasks=[
            TaskSpec(task_id="a", title="Task A", depends_on=[]),
            TaskSpec(task_id="a", title="Task A2", depends_on=[]),
        ],
    )

    with pytest.raises(ValueError, match="must be unique"):
        validate_submission(submission)


def test_validate_submission_rejects_unknown_dependencies() -> None:
    """Validates unknown dependency IDs raise a value error."""
    submission = SpecSubmission(
        spec_title="Title",
        spec_body="This body includes enough words for validation checks.",
        tasks=[TaskSpec(task_id="a", title="Task A", depends_on=["b"])],
    )

    with pytest.raises(ValueError, match="unknown task"):
        validate_submission(submission)


def test_validate_submission_rejects_invalid_request_type() -> None:
    """Validates invalid request type raises a value error."""
    submission = SpecSubmission(
        spec_title="Title",
        spec_body="This body includes enough words for validation checks.",
        request_type="other",
        tasks=[TaskSpec(task_id="a", title="Task A", depends_on=[])],
    )

    with pytest.raises(ValueError, match="request_type"):
        validate_submission(submission)

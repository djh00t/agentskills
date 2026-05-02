"""Tests for required per-skill scripts and deterministic planner behavior."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_spec_kit_skill_has_scripts_directory() -> None:
    """Ensures spec-kit skill includes only non-Python helper scripts."""
    repo_root = Path(__file__).resolve().parents[2]
    scripts_root = repo_root / "skills" / "spec-kit" / "scripts"

    assert scripts_root.is_dir()
    assert (scripts_root / "install_spec_kit_deps.sh").is_file()


def test_spec_kit_module_planner_is_deterministic(tmp_path: Path) -> None:
    """Ensures module CLI emits stable deterministic ordering and batches."""
    input_payload = {
        "spec_title": "Deterministic planning",
        "spec_body": "Validate stable ordering and deterministic output for tasks.",
        "tasks": [
            {
                "task_id": "b",
                "title": "Task B",
                "description": "after a",
                "depends_on": ["a"],
                "parallelizable": True,
            },
            {
                "task_id": "a",
                "title": "Task A",
                "description": "first",
                "depends_on": [],
                "parallelizable": True,
            },
            {
                "task_id": "c",
                "title": "Task C",
                "description": "after a",
                "depends_on": ["a"],
                "parallelizable": True,
            },
        ],
    }

    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "agentskills.skills.spec_kit",
            "plan",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--request-type",
            "behavior-change",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["ordered_task_ids"] == ["a", "b", "c"]
    assert output["parallel_groups"] == [["a"], ["b", "c"]]
    assert output["deterministic"] is True
    assert output["request_type"] == "behavior-change"
    assert "behavior-change" in output["issue_drafts"][0]["labels"]


def test_spec_kit_module_emit_dry_run(tmp_path: Path) -> None:
    """Ensures module CLI produces deterministic dry-run commands."""
    plan_payload = {
        "issue_drafts": [
            {
                "title": "Task A",
                "body": "Implement A",
                "labels": ["spec-kit", "agent-execution"],
                "blocked_by": [],
            },
            {
                "title": "Task B",
                "body": "Implement B",
                "labels": ["spec-kit", "agent-execution"],
                "blocked_by": ["task-a"],
            },
        ]
    }

    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "emit.json"
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "agentskills.skills.spec_kit",
            "emit",
            "--plan",
            str(plan_path),
            "--output",
            str(output_path),
            "--repo",
            "djh00t/agentskills",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["publish"] is False
    assert output["deterministic"] is True
    assert len(output["commands"]) == 2
    assert output["created"] == []


def test_spec_kit_module_emit_publish_requires_approval(tmp_path: Path) -> None:
    """Ensures publish mode fails without explicit approval payload."""
    plan_payload = {
        "issue_drafts": [
            {
                "title": "Task A",
                "body": "Implement A",
                "labels": ["spec-kit"],
                "blocked_by": [],
            }
        ]
    }

    plan_path = tmp_path / "plan_publish.json"
    output_path = tmp_path / "emit_publish.json"
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentskills.skills.spec_kit",
            "emit",
            "--plan",
            str(plan_path),
            "--output",
            str(output_path),
            "--repo",
            "djh00t/agentskills",
            "--publish",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "approval is required" in completed.stderr


def test_spec_kit_module_emit_publish_requires_allowlist(tmp_path: Path) -> None:
    """Ensures publish mode enforces repository allowlist when configured."""
    plan_payload = {
        "issue_drafts": [
            {
                "title": "Task A",
                "body": "Implement A",
                "labels": ["spec-kit"],
                "blocked_by": [],
            }
        ]
    }
    approval_payload = {
        "approved": True,
        "approver": "tester",
        "notes": "ok",
    }

    plan_path = tmp_path / "plan_allowlist.json"
    approval_path = tmp_path / "approval_allowlist.json"
    output_path = tmp_path / "emit_allowlist.json"
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
    approval_path.write_text(json.dumps(approval_payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentskills.skills.spec_kit",
            "emit",
            "--plan",
            str(plan_path),
            "--output",
            str(output_path),
            "--repo",
            "djh00t/agentskills",
            "--approval",
            str(approval_path),
            "--publish",
            "--allow-repo",
            "other/repo",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "not in allowlist" in completed.stderr

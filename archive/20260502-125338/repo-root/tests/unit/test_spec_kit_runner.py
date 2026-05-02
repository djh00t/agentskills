"""Unit tests for upstream Spec-Kit runner checks."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from agentskills.skills.spec_kit.runner import SpecKitRunner


def test_runner_fails_when_specify_missing() -> None:
    """Ensures missing specify CLI raises deterministic error."""
    runner = SpecKitRunner()
    with patch("agentskills.skills.spec_kit.runner.shutil.which", return_value=None):
        with pytest.raises(FileNotFoundError, match="specify CLI"):
            runner.ensure_available()


def test_runner_taskstoissues_ref_uses_specify_cli() -> None:
    """Ensures task-to-issues reference is CLI-based."""
    runner = SpecKitRunner()
    with patch(
        "agentskills.skills.spec_kit.runner.shutil.which",
        return_value="/usr/bin/specify",
    ):
        assert runner.taskstoissues_template_ref() == "specify-cli:taskstoissues"


def test_runner_uses_specify_cli_help_check() -> None:
    """Ensures upstream help checks call specify CLI."""
    runner = SpecKitRunner()

    with patch(
        "agentskills.skills.spec_kit.runner.shutil.which",
        return_value="/usr/bin/specify",
    ):
        with patch("agentskills.skills.spec_kit.runner.subprocess.run") as run_mock:
            run_mock.return_value.returncode = 0
            run_mock.return_value.stderr = ""
            runner.ensure_available()
            runner.run_upstream_help_checks()
            assert runner.taskstoissues_template_ref() == "specify-cli:taskstoissues"


def test_runner_help_check_failure_raises_runtime_error() -> None:
    """Ensures failed specify --help exits with deterministic runtime error."""
    runner = SpecKitRunner()

    with patch(
        "agentskills.skills.spec_kit.runner.shutil.which",
        return_value="/usr/bin/specify",
    ):
        with patch("agentskills.skills.spec_kit.runner.subprocess.run") as run_mock:
            run_mock.return_value.returncode = 1
            run_mock.return_value.stderr = "boom"
            with pytest.raises(RuntimeError, match="help check failed"):
                runner.run_upstream_help_checks()


def test_initialize_project_runs_specify_init_when_missing(tmp_path: Path) -> None:
    """Ensures init command runs when .specify is absent."""
    runner = SpecKitRunner()
    completed = subprocess.CompletedProcess(
        args=["specify"],
        returncode=0,
        stdout="",
        stderr="",
    )

    with patch(
        "agentskills.skills.spec_kit.runner.shutil.which",
        return_value="/usr/bin/specify",
    ):
        with patch(
            "agentskills.skills.spec_kit.runner.subprocess.run",
            return_value=completed,
        ) as run_mock:
            runner.initialize_project(tmp_path, "codex")
            run_mock.assert_called_once()


def test_initialize_project_skips_when_already_initialized(tmp_path: Path) -> None:
    """Ensures init command is skipped when .specify exists."""
    runner = SpecKitRunner()
    (tmp_path / ".specify").mkdir()

    with patch(
        "agentskills.skills.spec_kit.runner.shutil.which",
        return_value="/usr/bin/specify",
    ):
        with patch("agentskills.skills.spec_kit.runner.subprocess.run") as run_mock:
            runner.initialize_project(tmp_path, "codex")
            run_mock.assert_not_called()


def test_create_feature_and_setup_plan_parse_json(tmp_path: Path) -> None:
    """Ensures stage scripts parse upstream JSON payloads."""
    runner = SpecKitRunner()
    scripts = tmp_path / ".specify" / "scripts" / "bash"
    scripts.mkdir(parents=True)
    (scripts / "create-new-feature.sh").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )
    (scripts / "setup-plan.sh").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )

    create_output = (
        '{"BRANCH_NAME":"001-test","SPEC_FILE":"/tmp/spec.md","FEATURE_NUM":"001"}'
    )
    setup_output = (
        '{"FEATURE_SPEC":"/tmp/spec.md","IMPL_PLAN":"/tmp/plan.md",'
        '"SPECS_DIR":"/tmp","BRANCH":"001-test","HAS_GIT":true}'
    )
    with patch(
        "agentskills.skills.spec_kit.runner.subprocess.run",
        side_effect=[
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=create_output,
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=setup_output,
                stderr="",
            ),
        ],
    ):
        feature = runner.create_feature(tmp_path, "desc", "001-test")
        plan = runner.setup_plan(tmp_path, "001-test")

    assert feature["BRANCH_NAME"] == "001-test"
    assert feature["SPEC_FILE"] == "/tmp/spec.md"
    assert plan["SPECS_DIR"] == "/tmp"
    assert plan["HAS_GIT"] == "True"


def test_check_prerequisites_uses_feature_env(tmp_path: Path) -> None:
    """Ensures prerequisite checks include expected flags and feature env."""
    runner = SpecKitRunner()
    scripts = tmp_path / ".specify" / "scripts" / "bash"
    scripts.mkdir(parents=True)
    (scripts / "check-prerequisites.sh").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )

    with patch(
        "agentskills.skills.spec_kit.runner.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"ok": true}',
            stderr="",
        ),
    ) as run_mock:
        payload = runner.check_prerequisites(
            tmp_path,
            "001-test",
            include_tasks=True,
            require_tasks=True,
            paths_only=True,
        )

    assert payload["ok"] is True
    assert run_mock.call_args.kwargs["env"]["SPECIFY_FEATURE"] == "001-test"


def test_update_agent_context_runs_script(tmp_path: Path) -> None:
    """Ensures upstream agent context update script is executed."""
    runner = SpecKitRunner()
    scripts = tmp_path / ".specify" / "scripts" / "bash"
    scripts.mkdir(parents=True)
    (scripts / "update-agent-context.sh").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )

    with patch(
        "agentskills.skills.spec_kit.runner.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        ),
    ) as run_mock:
        runner.update_agent_context(tmp_path, "001-test", "codex")

    assert run_mock.call_args.kwargs["env"]["SPECIFY_FEATURE"] == "001-test"


def test_update_agent_context_raises_on_failure(tmp_path: Path) -> None:
    """Ensures failed update-agent-context invocation raises RuntimeError."""
    runner = SpecKitRunner()
    scripts = tmp_path / ".specify" / "scripts" / "bash"
    scripts.mkdir(parents=True)
    (scripts / "update-agent-context.sh").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )

    with patch(
        "agentskills.skills.spec_kit.runner.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="boom",
        ),
    ):
        with pytest.raises(RuntimeError, match="update-agent-context failed"):
            runner.update_agent_context(tmp_path, "001-test", "codex")


def test_script_path_raises_when_missing(tmp_path: Path) -> None:
    """Ensures missing initialized scripts raise FileNotFoundError."""
    runner = SpecKitRunner()
    with pytest.raises(FileNotFoundError, match="missing initialized script"):
        runner.create_feature(tmp_path, "desc", "001-test")

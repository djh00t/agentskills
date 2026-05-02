"""Adapter for invoking upstream Spec-Kit CLI assets."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


class SpecKitRunner:
    """Provides deterministic access to upstream Spec-Kit CLI."""

    def __init__(self) -> None:
        """Initializes runner."""

    def ensure_cli_available(self) -> None:
        """Validates that the upstream specify CLI is installed."""
        if shutil.which("specify") is None:
            msg = (
                "specify CLI is not installed. "
                "Run: uv tool install specify-cli --from "
                "git+https://github.com/github/spec-kit.git"
            )
            raise FileNotFoundError(msg)

    def ensure_available(self) -> None:
        """Validates that upstream CLI assets are available."""
        self.ensure_cli_available()

    def initialize_project(
        self,
        project_dir: Path,
        ai_assistant: str = "codex",
    ) -> None:
        """Initializes Spec-Kit artifacts in a project when required."""
        self.ensure_available()
        project_dir.mkdir(parents=True, exist_ok=True)

        if (project_dir / ".specify").exists():
            return

        completed = subprocess.run(
            [
                "specify",
                "init",
                "--here",
                "--ai",
                ai_assistant,
                "--ignore-agent-tools",
                "--force",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=project_dir,
        )
        if completed.returncode != 0:
            msg = f"specify init failed: {completed.stderr.strip()}"
            raise RuntimeError(msg)

    def create_feature(
        self,
        project_dir: Path,
        feature_description: str,
        short_name: str,
    ) -> dict[str, str]:
        """Creates feature artifacts using upstream create-new-feature script."""
        script = self._script_path(project_dir, "create-new-feature.sh")
        completed = subprocess.run(
            [
                "bash",
                str(script),
                "--json",
                "--short-name",
                short_name,
                feature_description,
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=project_dir,
        )
        if completed.returncode != 0:
            msg = f"create-new-feature failed: {completed.stderr.strip()}"
            raise RuntimeError(msg)

        payload = json.loads(completed.stdout)
        return {
            "BRANCH_NAME": str(payload["BRANCH_NAME"]),
            "SPEC_FILE": str(payload["SPEC_FILE"]),
            "FEATURE_NUM": str(payload["FEATURE_NUM"]),
        }

    def check_prerequisites(
        self,
        project_dir: Path,
        feature_name: str,
        include_tasks: bool = False,
        require_tasks: bool = False,
        paths_only: bool = False,
    ) -> dict[str, object]:
        """Runs upstream prerequisite checks for current feature."""
        script = self._script_path(project_dir, "check-prerequisites.sh")
        command = ["bash", str(script), "--json"]
        if include_tasks:
            command.append("--include-tasks")
        if require_tasks:
            command.append("--require-tasks")
        if paths_only:
            command.append("--paths-only")

        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=project_dir,
            env=self._with_feature_env(feature_name),
        )
        if completed.returncode != 0:
            msg = f"check-prerequisites failed: {completed.stderr.strip()}"
            raise RuntimeError(msg)
        return json.loads(completed.stdout)

    def setup_plan(self, project_dir: Path, feature_name: str) -> dict[str, str]:
        """Runs upstream setup-plan script to create plan artifacts."""
        script = self._script_path(project_dir, "setup-plan.sh")
        completed = subprocess.run(
            ["bash", str(script), "--json"],
            check=False,
            capture_output=True,
            text=True,
            cwd=project_dir,
            env=self._with_feature_env(feature_name),
        )
        if completed.returncode != 0:
            msg = f"setup-plan failed: {completed.stderr.strip()}"
            raise RuntimeError(msg)

        payload = json.loads(completed.stdout)
        return {
            "FEATURE_SPEC": str(payload["FEATURE_SPEC"]),
            "IMPL_PLAN": str(payload["IMPL_PLAN"]),
            "SPECS_DIR": str(payload["SPECS_DIR"]),
            "BRANCH": str(payload["BRANCH"]),
            "HAS_GIT": str(payload["HAS_GIT"]),
        }

    def update_agent_context(
        self,
        project_dir: Path,
        feature_name: str,
        agent_name: str,
    ) -> None:
        """Runs upstream agent-context update script for plan stage parity."""
        script = self._script_path(project_dir, "update-agent-context.sh")
        completed = subprocess.run(
            ["bash", str(script), agent_name],
            check=False,
            capture_output=True,
            text=True,
            cwd=project_dir,
            env=self._with_feature_env(feature_name),
        )
        if completed.returncode != 0:
            msg = f"update-agent-context failed: {completed.stderr.strip()}"
            raise RuntimeError(msg)

    def verify_workflow_assets(self) -> None:
        """Validates required upstream CLI assets are available."""
        self.ensure_available()

    def run_upstream_help_checks(self) -> None:
        """Runs upstream CLI help command to verify executable toolchain."""
        self.verify_workflow_assets()
        completed = subprocess.run(
            ["specify", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            msg = f"specify CLI help check failed: {completed.stderr.strip()}"
            raise RuntimeError(msg)

    def taskstoissues_template_ref(self) -> str:
        """Returns canonical upstream task-to-issues command reference."""
        self.ensure_available()
        return "specify-cli:taskstoissues"

    def _script_path(self, project_dir: Path, script_name: str) -> Path:
        """Resolves initialized upstream script path in target project."""
        script = project_dir / ".specify" / "scripts" / "bash" / script_name
        if not script.is_file():
            msg = f"missing initialized script: {script}"
            raise FileNotFoundError(msg)
        return script

    def _with_feature_env(self, feature_name: str) -> dict[str, str]:
        """Builds environment with SPECIFY_FEATURE for script execution."""
        env = os.environ.copy()
        env["SPECIFY_FEATURE"] = feature_name
        return env

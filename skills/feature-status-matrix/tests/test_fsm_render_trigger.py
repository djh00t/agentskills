"""Subprocess checks for renders used by short-lived ledger processes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fsm_ledger.metered import metered_call

SKILL = Path(__file__).resolve().parents[1]
CODEX_HOOK = SKILL / "harnesses" / "codex" / ".codex-plugin" / "fsm-ledger-hook"


class ProcessBoundRenderTest(unittest.TestCase):
    def test_feature_scenarios(self):
        scenarios = {
            "Codex Stop captures in the background": self._codex_stop,
            "SessionEnd survives until the next Stop": self._session_end,
            "CLI append renders after exit": self._cli_render,
            "Metered calls do not retry internal errors": self._metered_error,
        }
        feature = (SKILL / "features/fsm_ledger.feature").read_text(encoding="utf-8")
        names = [line.removeprefix("Scenario:").strip() for line in feature.splitlines()
                 if line.startswith("Scenario:")]
        self.assertEqual(set(names), set(scenarios))
        for name in names:
            with self.subTest(name=name):
                scenarios[name]()

    def _env(self, root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "FSM_MATRICES_ROOT": str(root),
                "FSM_PROJECT": "agent-brain",
                "PYTHONPATH": str(SKILL),
            }
        )
        return env

    def _setup_project(self, root: Path) -> Path:
        project = root / "agent-brain"
        project.mkdir(parents=True)
        (project / "project.json").write_text(
            json.dumps({"id": "agent-brain", "roots": [str(SKILL)]}) + "\n",
            encoding="utf-8",
        )
        (project / "work-packages.json").write_text(
            json.dumps(
                [
                    {
                        "id": "AB-033",
                        "theme": "Enrich-S3",
                        "wave": 1,
                        "size": "S",
                        "title": "Render hook",
                        "state": "IN_PROGRESS",
                    }
                ]
            ),
            encoding="utf-8",
        )
        return project

    def _codex_stop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = self._setup_project(root)
            hooks = json.loads((SKILL / "harnesses/codex/.codex-plugin/hooks.json").read_text())
            self.assertTrue(hooks["hooks"]["Stop"][0]["hooks"][0]["async"])
            proc = subprocess.run(
                [str(CODEX_HOOK), "stop"],
                input=json.dumps(
                    {
                        "cwd": str(SKILL),
                        "model": "gpt-6-luna",
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                        "message_id": "hook-render",
                    }
                ),
                env=self._env(root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            deadline = time.monotonic() + 10
            while not (project / "FEATURE_STATUS_MATRIX.md").is_file() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((project / "FEATURE_STATUS_MATRIX.md").is_file())

    def _session_end(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = self._setup_project(root)
            payload = {
                "cwd": str(SKILL),
                "model": "gpt-6-luna",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "message_id": "session-end-capture",
            }
            end = subprocess.run(
                [str(CODEX_HOOK), "session_end"],
                input=json.dumps(payload), env=self._env(root), capture_output=True,
                text=True, timeout=3,
            )
            self.assertEqual(end.returncode, 0, end.stderr)
            self.assertFalse((project / "usage.jsonl").exists())
            self.assertEqual(len(list((root / "_hook_pending").glob("event-*"))), 1)
            stop = subprocess.run(
                [str(CODEX_HOOK), "stop"],
                input=json.dumps({"cwd": str(SKILL)}), env=self._env(root),
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(stop.returncode, 0, stop.stderr)
            rows = [json.loads(line) for line in (project / "usage.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["message_id"], "session-end-capture")
            self.assertFalse(list((root / "_hook_pending").glob("event-*")))

    def _cli_render(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = self._setup_project(root)
            proc = subprocess.run(
                [sys.executable, "-m", "fsm_ledger", "append", "--project", "agent-brain",
                 "--render", "--json", json.dumps({"workPackageId": "AB-033",
                    "inputTokens": 10, "outputTokens": 5, "costTotal": 0.01})],
                cwd=str(SKILL), env=self._env(root), capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            deadline = time.monotonic() + 10
            while not (project / "FEATURE_STATUS_MATRIX.md").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((project / "FEATURE_STATUS_MATRIX.md").is_file())

    def _metered_error(self):
        calls = []

        @metered_call()
        def raises_after_side_effect(*, meter):
            calls.append(1)
            raise TypeError("from inside function")

        with self.assertRaisesRegex(TypeError, "from inside function"):
            raises_after_side_effect()
        self.assertEqual(len(calls), 1)

if __name__ == "__main__":
    unittest.main()

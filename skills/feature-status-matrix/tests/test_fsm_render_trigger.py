"""Subprocess checks for renders used by short-lived ledger processes."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
CODEX_HOOK = SKILL / "harnesses" / "codex" / ".codex-plugin" / "fsm-ledger-hook"


class ProcessBoundRenderTest(unittest.TestCase):
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

    def test_codex_hook_accepts_then_renders_in_background(self):
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

    def test_session_end_is_durable_until_next_stop(self):
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

if __name__ == "__main__":
    unittest.main()

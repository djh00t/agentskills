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

from fsm_ledger.render_trigger import render_now


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

    def _rollout(self, root: Path) -> Path:
        path = root / "rollout.jsonl"
        rows = [
            {"type": "session_meta", "payload": {"session_id": "render-session", "cwd": str(SKILL)}},
            {"type": "turn_context", "payload": {"turn_id": "turn-1", "model": "gpt-6-luna"}},
            {"type": "token_usage_record", "timestamp": "2026-09-28T01:02:03Z", "payload": {
                "session_id": "render-session", "turn_id": "turn-1", "response_id": "response-1",
                "usage": {"input_tokens": 10, "output_tokens": 5, "cached_input_tokens": 0,
                          "cache_write_input_tokens": 0, "total_tokens": 15},
            }},
        ]
        path.write_text("\n".join(map(json.dumps, rows)) + "\n", encoding="utf-8")
        return path

    def test_append_cli_renders_before_process_exit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = self._setup_project(root)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "fsm_ledger",
                    "append",
                    "--project",
                    "agent-brain",
                    "--render",
                    "--json",
                    json.dumps(
                        {
                            "workPackageId": "AB-033",
                            "inputTokens": 10,
                            "outputTokens": 5,
                            "costTotal": 0.01,
                            "message_id": "cli-render",
                        }
                    ),
                ],
                cwd=str(SKILL),
                env=self._env(root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((project / "FEATURE_STATUS_MATRIX.md").is_file())

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
                        "session_id": "render-session",
                        "transcript_path": str(self._rollout(root)),
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

    def test_session_end_drains_its_rollout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = self._setup_project(root)
            payload = {
                "cwd": str(SKILL),
                "session_id": "render-session",
                "transcript_path": str(self._rollout(root)),
            }
            end = subprocess.run(
                [str(CODEX_HOOK), "session_end"],
                input=json.dumps(payload), env=self._env(root), capture_output=True,
                text=True, timeout=3,
            )
            self.assertEqual(end.returncode, 0, end.stderr)
            rows = [json.loads(line) for line in (project / "usage.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event_id"], "codex:render-session:response-1")
            self.assertFalse(list((root / "_hook_pending").glob("event-*")))

    def test_render_rejects_project_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "matrices"
            outside = Path(td) / "escape"
            root.mkdir()
            outside.mkdir()
            (outside / "work-packages.json").write_text("[]\n", encoding="utf-8")
            old_root = os.environ.get("FSM_MATRICES_ROOT")
            os.environ["FSM_MATRICES_ROOT"] = str(root)
            try:
                result = render_now("../escape")
            finally:
                if old_root is None:
                    os.environ.pop("FSM_MATRICES_ROOT", None)
                else:
                    os.environ["FSM_MATRICES_ROOT"] = old_root
            self.assertFalse(result["ok"])
            self.assertFalse((outside / "FEATURE_STATUS_MATRIX.md").exists())


if __name__ == "__main__":
    unittest.main()

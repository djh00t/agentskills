\
"""Render FEATURE_STATUS_MATRIX.md without blocking short-lived callers."""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Optional

from .attribute import matrices_root
from .ledger import _log

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_RENDER_SCRIPT = _SKILL_ROOT / "tools" / "render_matrix.py"

def _project_paths(project: str) -> dict[str, Path]:
    root = matrices_root() / project
    return {
        "root": root,
        "packages": root / "work-packages.json",
        "usage": root / "usage.jsonl",
        "state": root / "status-matrix-state.json",
        "out": root / "FEATURE_STATUS_MATRIX.md",
    }


def render_now(project: str, *, mode: str = "full", area: Optional[str] = None) -> dict:
    """Run render_matrix synchronously. Returns result dict; never raises."""
    try:
        paths = _project_paths(project)
        if not paths["packages"].exists():
            return {"ok": False, "error": f"missing {paths['packages']}"}
        cmd = [
            sys.executable,
            str(_RENDER_SCRIPT),
            "--packages-json",
            str(paths["packages"]),
            "--usage-log",
            str(paths["usage"]),
            "--state-file",
            str(paths["state"]),
            "--out",
            str(paths["out"]),
            "--mode",
            mode,
        ]
        if area:
            cmd.extend(["--area", area])
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_SKILL_ROOT / "tools") + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if proc.returncode != 0:
            _log(f"render_fail project={project} rc={proc.returncode} err={proc.stderr[-500:]}")
            return {"ok": False, "error": proc.stderr or proc.stdout, "rc": proc.returncode}
        _log(f"render_ok project={project} mode={mode}")
        return {"ok": True, "stdout": proc.stdout, "out": str(paths["out"])}
    except Exception as exc:  # noqa: BLE001
        _log(f"render_error project={project} err={exc}\n{traceback.format_exc()}")
        return {"ok": False, "error": str(exc)}


def schedule_render(project: str, *, mode: str = "full") -> None:
    """Start a render process that survives a short-lived hook or CLI."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SKILL_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.Popen(
        [sys.executable, "-m", "fsm_ledger", "render", "--project", project, "--mode", mode],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )

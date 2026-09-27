\
"""Resolve project + work-package for a usage event."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from .schema import UNALLOCATED

STATUS_MATRICES_ROOT = Path.home() / ".agents" / "status-matrices"



def matrices_root() -> Path:
    env = os.environ.get("FSM_MATRICES_ROOT")
    return Path(env).expanduser() if env else STATUS_MATRICES_ROOT


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def list_projects() -> list[str]:
    root = matrices_root()
    if not root.is_dir():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "project.json").exists()
    )


def load_project_config(project: str) -> dict[str, Any]:
    return _read_json(matrices_root() / project / "project.json")


def _git(cwd: Path, *args: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=str(cwd),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return out.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def resolve_project(cwd: Optional[str] = None, hint: Optional[str] = None) -> str:
    """Resolve project id from hint, cwd roots, git remote, or basename heuristic."""
    if hint:
        return hint
    env = os.environ.get("FSM_PROJECT") or os.environ.get("FEATURE_PROJECT")
    if env:
        return env.strip()

    cwd_path = Path(cwd or os.environ.get("PWD") or os.getcwd()).resolve()

    # 1) cwd under roots in project.json
    root = matrices_root()
    if root.is_dir():
        for proj_dir in sorted(root.iterdir()):
            cfg = _read_json(proj_dir / "project.json")
            for r in cfg.get("roots") or []:
                try:
                    rp = Path(r).expanduser().resolve()
                    if cwd_path == rp or rp in cwd_path.parents:
                        return str(cfg.get("id") or proj_dir.name)
                except OSError:
                    continue
            # also: cwd path contains project id as segment
            remote_contains = str(cfg.get("remote_contains") or "")
            if remote_contains:
                remote = _git(cwd_path, "remote", "get-url", "origin")
                if remote_contains in remote:
                    return str(cfg.get("id") or proj_dir.name)

    # 2) git remote match without project.json
    remote = _git(cwd_path, "remote", "get-url", "origin")
    if "agent-brain" in remote:
        return "agent-brain"

    # 3) basename heuristic
    name = cwd_path.name
    if name in ("agent-brain", "agent-brain-poc"):
        return "agent-brain"
    # walk up a few levels
    for parent in list(cwd_path.parents)[:4]:
        if parent.name in ("agent-brain", "agent-brain-poc"):
            return "agent-brain"

    return "agent-brain"  # safe default for this user's primary matrix


def _wp_from_branch_or_subject(text: str) -> Optional[str]:
    if not text:
        return None
    # Prefer explicit ticket ids anywhere (AB-033) before feat() slug mapping
    ticket = re.search(r"\b([A-Z]{1,8}-\d{1,5})\b", text, re.IGNORECASE)
    if ticket:
        return ticket.group(1).upper()
    m = re.search(r"feat[/(]([a-zA-Z0-9._-]+)[)]?", text, re.IGNORECASE)
    if not m:
        return None
    slug = (m.group(1) or "").strip("-_/")
    if not slug:
        return None
    # Ticket embedded in slug: AB-033-videos
    embedded = re.search(r"([A-Za-z]{1,8}-\d{1,5})", slug)
    if embedded:
        return embedded.group(1).upper()
    slug_l = slug.lower()
    if slug_l in ("enrich", "enrich-s3", "enrich_s3", "videos", "yt-dlp"):
        return "AB-033"
    if re.fullmatch(r"[A-Za-z]{1,8}-\d{1,5}", slug):
        return slug.upper()
    return None


def resolve_work_package(
    *,
    cwd: Optional[str] = None,
    project: Optional[str] = None,
    explicit: Optional[str] = None,
) -> str:
    """Resolve WP id: env → active-wp.json → branch/subject heuristic → UNALLOCATED."""
    if explicit:
        return explicit

    # 1) Env
    for key in ("FSM_WP", "FEATURE_WP"):
        val = os.environ.get(key)
        if val and val.strip():
            return val.strip()

    proj = project or resolve_project(cwd)
    cwd_path = Path(cwd or os.environ.get("PWD") or os.getcwd()).resolve()

    # 2) active-wp.json
    active_path = matrices_root() / proj / "active-wp.json"
    active = _read_json(active_path)
    wp = active.get("workPackageId") or active.get("wp") or active.get("id")
    if wp:
        return str(wp)

    # 3) Branch / commit subject heuristic
    branch = _git(cwd_path, "rev-parse", "--abbrev-ref", "HEAD")
    found = _wp_from_branch_or_subject(branch)
    if found:
        return found
    subject = _git(cwd_path, "log", "-1", "--pretty=%s")
    found = _wp_from_branch_or_subject(subject)
    if found:
        return found

    # 4) Else UNALLOCATED
    return UNALLOCATED


def bind_active_wp(project: str, wp: str) -> Path:
    """Write active-wp.json for a project."""
    path = matrices_root() / project / "active-wp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"workPackageId": wp, "project": project}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def resolve_attribution(
    *,
    cwd: Optional[str] = None,
    project: Optional[str] = None,
    wp: Optional[str] = None,
) -> dict[str, str]:
    proj = project or resolve_project(cwd)
    work = resolve_work_package(cwd=cwd, project=proj, explicit=wp)
    return {"project": proj, "workPackageId": work}

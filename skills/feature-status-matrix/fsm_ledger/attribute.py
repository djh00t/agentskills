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
UNKNOWN_PROJECT = "_unattributed"
_PROJECT_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")



def matrices_root() -> Path:
    env = os.environ.get("FSM_MATRICES_ROOT")
    return Path(env).expanduser() if env else STATUS_MATRICES_ROOT


def _safe_project(value: Any) -> Optional[str]:
    """Return a filesystem-safe project slug, or None for empty/invalid input."""
    text = str(value).strip() if value is not None else ""
    return text if _PROJECT_SLUG.fullmatch(text) else None


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
    safe = _safe_project(project)
    return _read_json(matrices_root() / safe / "project.json") if safe else {}


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


def _project_from_cwd(cwd: Optional[str]) -> tuple[Optional[str], bool]:
    """Resolve a project from configured roots or its git remote."""
    try:
        raw_cwd = cwd if cwd is not None and str(cwd).strip() else os.environ.get("PWD") or os.getcwd()
        cwd_path = Path(raw_cwd).expanduser().resolve()
    except (OSError, RuntimeError):
        return None, False
    if not cwd_path.exists():
        return None, False

    # 1) cwd under roots in project.json
    root = matrices_root()
    if root.is_dir():
        for proj_dir in sorted(root.iterdir()):
            cfg = _read_json(proj_dir / "project.json")
            for r in cfg.get("roots") or []:
                try:
                    rp = Path(r).expanduser().resolve()
                    if cwd_path == rp or rp in cwd_path.parents:
                        return _safe_project(cfg.get("id")) or _safe_project(proj_dir.name), True
                except OSError:
                    continue
            # also: cwd path contains project id as segment
            remote_contains = str(cfg.get("remote_contains") or "")
            if remote_contains:
                remote = _git(cwd_path, "remote", "get-url", "origin")
                if remote_contains in remote:
                    return _safe_project(cfg.get("id")) or _safe_project(proj_dir.name), True

    return None, True


def resolve_project(cwd: Optional[str] = None, hint: Optional[str] = None) -> str:
    """Resolve project, rejecting a hint that conflicts with a known cwd."""
    detected, cwd_available = _project_from_cwd(cwd)
    env = os.environ.get("FSM_PROJECT") or os.environ.get("FEATURE_PROJECT")
    candidate = hint if hint is not None and str(hint).strip() else env
    if candidate is not None and str(candidate).strip():
        hinted = _safe_project(candidate)
        if detected:
            return detected if hinted == detected else UNKNOWN_PROJECT
        if cwd_available:
            return UNKNOWN_PROJECT
        return hinted or UNKNOWN_PROJECT
    if detected:
        return detected

    # Unknown global events must remain auditable without contaminating a project.
    return UNKNOWN_PROJECT


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

    proj = resolve_project(cwd, hint=project) if project is not None else resolve_project(cwd)
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
    path = matrices_root() / (_safe_project(project) or UNKNOWN_PROJECT) / "active-wp.json"
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
    proj = resolve_project(cwd, hint=project) if project is not None else resolve_project(cwd)
    work = resolve_work_package(cwd=cwd, project=proj, explicit=wp)
    return {"project": proj, "workPackageId": work}

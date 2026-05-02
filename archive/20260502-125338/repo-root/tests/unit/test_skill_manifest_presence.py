"""Repository guardrails for required per-skill manifest files."""

from __future__ import annotations

from pathlib import Path


def test_each_skill_has_required_files() -> None:
    """Ensures each skill directory has SKILL.md and AGENTS.md."""
    repo_root = Path(__file__).resolve().parents[2]
    skills_root = repo_root / "skills"

    skill_dirs = sorted(
        path
        for path in skills_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )
    assert skill_dirs, "At least one skill directory is required"

    for skill_dir in skill_dirs:
        skill_manifest = skill_dir / "SKILL.md"
        skill_agents = skill_dir / "AGENTS.md"
        assert skill_manifest.exists(), f"Missing SKILL.md in {skill_dir.name}"
        assert skill_agents.exists(), f"Missing AGENTS.md in {skill_dir.name}"

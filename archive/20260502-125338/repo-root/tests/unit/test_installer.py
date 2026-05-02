"""Unit tests for agentskills installer module."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from agentskills.installer import (
    _parse_github_owner_repo,
    _resolve_scope_target,
    _select_scope_interactive,
    _select_skills_interactive,
    _validate_skill_layout,
    build_parser,
    install_skills,
    list_available_skills,
    run_install,
)


def _build_source_tree(tmp_path: Path) -> Path:
    """Builds a minimal source repository tree with one valid skill."""
    source_root = tmp_path / "source"
    skill_root = source_root / "skills" / "spec-kit"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("name: spec-kit", encoding="utf-8")
    (skill_root / "AGENTS.md").write_text("agents", encoding="utf-8")
    (skill_root / "scripts" / "run.sh").write_text("#!/bin/sh", encoding="utf-8")
    return source_root


def test_list_available_skills(tmp_path: Path) -> None:
    """Ensures installer lists skills from source tree deterministically."""
    source_root = _build_source_tree(tmp_path)
    skills = list_available_skills(source_root / "skills")
    assert skills == ["spec-kit"]


def test_install_skills_repo_scope(tmp_path: Path) -> None:
    """Ensures installer copies selected skills into repo-local target."""
    source_root = _build_source_tree(tmp_path)
    repo_dir = tmp_path / "workspace"
    repo_dir.mkdir(parents=True)

    installed = install_skills(
        source_root=source_root,
        selected_skills=["spec-kit"],
        scope="repo",
        repo_dir=str(repo_dir),
        force=True,
    )

    expected = repo_dir / ".agents" / "skills" / "spec-kit"
    assert installed == [expected]
    assert (expected / "SKILL.md").is_file()
    assert (expected / "AGENTS.md").is_file()


def test_parse_github_owner_repo() -> None:
    """Ensures owner/repo parsing supports standard GitHub URL forms."""
    assert _parse_github_owner_repo("https://github.com/djh00t/agentskills") == (
        "djh00t",
        "agentskills",
    )
    assert _parse_github_owner_repo("https://github.com/djh00t/agentskills.git") == (
        "djh00t",
        "agentskills",
    )


def test_parse_github_owner_repo_rejects_non_github() -> None:
    """Ensures only GitHub URLs are accepted by archive downloader."""
    with pytest.raises(ValueError, match="github.com"):
        _parse_github_owner_repo("https://example.com/repo")


def test_validate_skill_layout_errors(tmp_path: Path) -> None:
    """Ensures layout validator catches missing required skill files."""
    skill_root = tmp_path / "skills" / "spec-kit"
    skill_root.mkdir(parents=True)

    with pytest.raises(ValueError, match="SKILL.md"):
        _validate_skill_layout(skill_root)

    (skill_root / "SKILL.md").write_text("name: spec-kit", encoding="utf-8")
    with pytest.raises(ValueError, match="AGENTS.md"):
        _validate_skill_layout(skill_root)

    (skill_root / "AGENTS.md").write_text("agents", encoding="utf-8")
    with pytest.raises(ValueError, match="scripts"):
        _validate_skill_layout(skill_root)


def test_resolve_scope_target_repo(tmp_path: Path) -> None:
    """Ensures repo scope resolves into .agents/skills path."""
    target = _resolve_scope_target("repo", str(tmp_path))
    assert target == tmp_path / ".agents" / "skills"


def test_resolve_scope_target_invalid() -> None:
    """Ensures invalid scope is rejected."""
    with pytest.raises(ValueError, match="invalid scope"):
        _resolve_scope_target("bad", None)


def test_select_scope_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures interactive scope selection maps numeric choices."""
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert _select_scope_interactive() == "global"


def test_select_skills_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures interactive skill selection parses comma indexes."""
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert _select_skills_interactive(["spec-kit"]) == ["spec-kit"]


def test_build_parser_install_subcommand() -> None:
    """Ensures parser defines install subcommand and binds function."""
    parser = build_parser()
    args = parser.parse_args(["install", "--skills", "spec-kit", "--scope", "global"])
    assert args.command == "install"
    assert args.skills == "spec-kit"
    assert callable(args.func)


def test_run_install_with_source_dir(tmp_path: Path) -> None:
    """Ensures run_install installs selected skill from local source dir."""
    source_root = _build_source_tree(tmp_path)
    repo_dir = tmp_path / "workspace"
    repo_dir.mkdir(parents=True)

    args = argparse.Namespace(
        command="install",
        skills="spec-kit",
        scope="repo",
        repo_dir=str(repo_dir),
        repo_url="https://github.com/djh00t/agentskills",
        ref="main",
        force=True,
        source_dir=str(source_root),
    )

    assert run_install(args) == 0
    assert (repo_dir / ".agents" / "skills" / "spec-kit" / "SKILL.md").is_file()

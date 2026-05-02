"""Installer utilities for copying skills from repository sources."""

from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve  # noqa: S310

DEFAULT_REPO_URL = "https://github.com/djh00t/agentskills"
DEFAULT_REPO_REF = "main"


def list_available_skills(skills_root: Path) -> list[str]:
    """Lists available skills under a source skills root."""
    if not skills_root.is_dir():
        msg = f"skills directory not found: {skills_root}"
        raise FileNotFoundError(msg)
    return sorted(path.name for path in skills_root.iterdir() if path.is_dir())


def _parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    """Parses a GitHub owner/repo tuple from repository URL."""
    parsed = urlparse(repo_url)
    host = parsed.netloc.lower()
    if host not in {"github.com", "www.github.com"}:
        msg = "only github.com repository URLs are supported"
        raise ValueError(msg)

    path_parts = [item for item in parsed.path.strip("/").split("/") if item]
    if len(path_parts) < 2:
        msg = f"invalid GitHub repository URL: {repo_url}"
        raise ValueError(msg)

    owner = path_parts[0]
    repo = path_parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _download_source_archive(repo_url: str, ref: str, tmp_root: Path) -> Path:
    """Downloads and extracts a GitHub tarball archive into a temp directory."""
    owner, repo = _parse_github_owner_repo(repo_url)
    archive_url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{ref}"

    archive_path = tmp_root / "source.tar.gz"
    urlretrieve(archive_url, archive_path)

    extract_root = tmp_root / "src"
    extract_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(extract_root)

    extracted_dirs = [path for path in extract_root.iterdir() if path.is_dir()]
    if len(extracted_dirs) != 1:
        msg = "unable to determine extracted repository root"
        raise RuntimeError(msg)
    return extracted_dirs[0]


def _validate_skill_layout(skill_dir: Path) -> None:
    """Ensures required files/directories exist in skill source directory."""
    if not (skill_dir / "SKILL.md").is_file():
        msg = f"skill '{skill_dir.name}' is missing required SKILL.md"
        raise ValueError(msg)
    if not (skill_dir / "AGENTS.md").is_file():
        msg = f"skill '{skill_dir.name}' is missing required AGENTS.md"
        raise ValueError(msg)
    if not (skill_dir / "scripts").is_dir():
        msg = f"skill '{skill_dir.name}' is missing required scripts/ directory"
        raise ValueError(msg)


def _resolve_scope_target(scope: str, repo_dir: str | None) -> Path:
    """Resolves destination base path for global or repository scope."""
    if scope == "global":
        return Path.home() / ".agents" / "skills"
    if scope == "repo":
        root = Path(repo_dir) if repo_dir else Path.cwd()
        return root / ".agents" / "skills"
    msg = f"invalid scope: {scope}"
    raise ValueError(msg)


def _select_skills_interactive(available_skills: list[str]) -> list[str]:
    """Prompts for one or more skills interactively."""
    print("Available skills:")
    for index, skill in enumerate(available_skills, start=1):
        print(f"  {index}) {skill}")

    raw = input("Select one or more skills (comma numbers, or 'all'): ").strip()
    if raw == "all":
        return available_skills

    selected: list[str] = []
    for token in raw.split(","):
        item = token.strip()
        if not item.isdigit():
            msg = f"invalid selection token: {item}"
            raise ValueError(msg)
        idx = int(item) - 1
        if idx < 0 or idx >= len(available_skills):
            msg = f"selection out of range: {item}"
            raise ValueError(msg)
        selected.append(available_skills[idx])
    return list(dict.fromkeys(selected))


def _select_scope_interactive() -> str:
    """Prompts for install scope interactively."""
    print("Choose install scope:")
    print("  1) global (~/.agents/skills)")
    print("  2) repo   (<repo>/.agents/skills)")
    choice = input("Enter choice [1-2]: ").strip()
    if choice == "1":
        return "global"
    if choice == "2":
        return "repo"
    msg = f"invalid scope choice: {choice}"
    raise ValueError(msg)


def install_skills(
    source_root: Path,
    selected_skills: list[str],
    scope: str,
    repo_dir: str | None,
    force: bool,
) -> list[Path]:
    """Installs selected skills from source root into resolved destination."""
    skills_root = source_root / "skills"
    available = list_available_skills(skills_root)

    for skill in selected_skills:
        if skill not in available:
            msg = f"unknown skill requested: {skill}"
            raise ValueError(msg)

    target_base = _resolve_scope_target(scope, repo_dir)
    target_base.mkdir(parents=True, exist_ok=True)

    installed: list[Path] = []
    for skill in selected_skills:
        src_dir = skills_root / skill
        dst_dir = target_base / skill
        _validate_skill_layout(src_dir)

        if dst_dir.exists():
            if force:
                shutil.rmtree(dst_dir)
            else:
                overwrite = input(
                    f"Skill '{skill}' already exists. Overwrite? [y/N]: "
                ).strip()
                if overwrite.lower() != "y":
                    print(f"Skipping {skill}")
                    continue
                shutil.rmtree(dst_dir)

        shutil.copytree(src_dir, dst_dir)
        print(f"Installed: {skill} -> {dst_dir}")
        installed.append(dst_dir)

    return installed


def run_install(args: argparse.Namespace) -> int:
    """Executes install command from parsed CLI arguments."""
    scope = args.scope or _select_scope_interactive()
    if scope not in {"global", "repo"}:
        msg = f"invalid scope: {scope}"
        raise ValueError(msg)

    source_override = args.source_dir
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        if source_override:
            source_root = Path(source_override).resolve()
        else:
            print(f"Downloading {args.repo_url} ({args.ref})...")
            source_root = _download_source_archive(args.repo_url, args.ref, temp_root)

        available = list_available_skills(source_root / "skills")
        if not available:
            msg = "no installable skills found"
            raise ValueError(msg)

        if args.skills:
            selected = [item.strip() for item in args.skills.split(",") if item.strip()]
            selected = list(dict.fromkeys(selected))
        else:
            selected = _select_skills_interactive(available)

        if not selected:
            msg = "no skills selected for installation"
            raise ValueError(msg)

        target_base = _resolve_scope_target(scope, args.repo_dir)
        print(f"Installing to: {target_base}")
        install_skills(
            source_root=source_root,
            selected_skills=selected,
            scope=scope,
            repo_dir=args.repo_dir,
            force=bool(args.force),
        )
    print("Done.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Builds top-level agentskills CLI parser."""
    parser = argparse.ArgumentParser(prog="agentskills")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Install one or more skills")
    install_parser.add_argument("--skills", help="Comma-separated skills")
    install_parser.add_argument(
        "--scope",
        choices=["global", "repo"],
        help="Install scope",
    )
    install_parser.add_argument(
        "--repo-dir",
        help="Repository target path when --scope repo (default: cwd)",
    )
    install_parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help="Source repository URL",
    )
    install_parser.add_argument(
        "--ref",
        default=DEFAULT_REPO_REF,
        help="Source repository ref",
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing installed skills without prompt",
    )
    install_parser.add_argument(
        "--source-dir",
        help=argparse.SUPPRESS,
    )
    install_parser.set_defaults(func=run_install)

    return parser

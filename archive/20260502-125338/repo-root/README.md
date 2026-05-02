# agentskills

Agent-first monorepo for reusable agent skills and deterministic orchestration.

## Goals

- Keep skill behavior deterministic and contract-driven.
- Keep humans in control at clarification and approval checkpoints.
- Reuse upstream tools and templates directly when possible.
- Publish approved execution work as GitHub issues for downstream agents.

## Repository Layout

- `AGENTS.md`: root operating contract for all agents in this repo.
- `skills/`: skill definitions and per-skill agent guidance.
- `src/agentskills/`: typed Python implementation modules.
- `tests/`: BDD features, unit tests, and integration tests.
- `docs/`: architecture, runbooks, contracts, and operational guidance.

## Quickstart

1. Create and activate a UV-managed virtual environment:
   - `uv venv`
2. Install project and dev dependencies from `pyproject.toml`:
   - `uv sync --extra dev`
3. Run checks:
   - `uv run make check`

The `check` target includes Agent Skills spec validation via:

- `uvx --from skills-ref agentskills validate skills/spec-kit`

## First Skill: spec-kit

The first skill wraps GitHub Spec-Kit deterministically while preserving the
documented Spec-Kit process. See:

- `skills/spec-kit/README.md`
- `skills/spec-kit/AGENTS.md`
- `docs/spec_kit_runbook.md`

## Upstream Sync

Use the upstream CLI/tooling workflow in `docs/upstream-sync.md`.

## Skill Installer

Install one or more skills directly from this repository using `uvx`:

- Interactive installer:
  - `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install`
- Install `spec-kit` globally to `~/.agents/skills/spec-kit`:
  - `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install --skills spec-kit --scope global`
- Install `spec-kit` into current repo at `.agents/skills/spec-kit`:
  - `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install --skills spec-kit --scope repo --repo-dir .`

The hosted shell bootstrap remains available and forwards to the same `uvx`
command:

- `curl -fsSL https://raw.githubusercontent.com/djh00t/agentskills/main/install.sh | bash`

If `uv`/`uvx` are not installed, the bootstrap script installs `uv` first.

The installer downloads a temporary GitHub source archive for the selected ref,
copies selected skills into the chosen target scope, and cleans up temporary
files automatically.

## Spec-Kit Requirements

Install upstream Spec-Kit CLI directly with UV:

1. `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`
2. `specify --help`

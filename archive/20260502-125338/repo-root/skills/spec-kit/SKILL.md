---
name: spec-kit
description: Deterministic wrapper around GitHub Spec-Kit with human clarification and approval gates before issue publication. A project management & execution tool for transforming human specifications into structured execution plans and GitHub issues while adhering to the upstream Spec-Kit process.
compatibility: agents
metadata:
  scope: skill
  install_path_global: ~/.agents/skills/spec-kit
  install_path_repo: .agents/skills/spec-kit
---

## What this skill does

- Uses upstream Spec-Kit CLI and process.
- Accepts human specifications and normalizes them into stable contracts.
- Builds dependency-aware execution ordering and deterministic parallel batches.
- Runs upstream plan-stage agent context updates and emits plan artifacts
  (`research.md`, `data-model.md`, `contracts/`, `quickstart.md`).
- Performs deterministic analysis and auto-fix for common artifact consistency
  gaps before issue handoff.
- Bootstraps a minimal deterministic task chain when explicit tasks are absent.
- Requires explicit human approval before creating or updating GitHub issues.

## Inputs

- `spec_title`: short title.
- `spec_body`: full specification text.
- `request_type` (optional): `new-feature` or `behavior-change`
- `project_dir` (optional): target repository directory for upstream `.specify` initialization and stage scripts (defaults to `.`).
- `ai_assistant` (optional): assistant profile passed to `specify init --ai` (defaults to `codex`).
- `tasks` (optional): pre-seeded task list with dependencies.
- `dry_run` (optional): defaults to `true`.

## Outputs

- deterministic execution plan
- ordered tasks and parallel groups
- issue drafts and, after approval, published issue references

## Required behavior

1. Do not invent templates, stages, or workflow variants.
2. Follow documented upstream Spec-Kit flow.
3. Ask clarifying questions when required inputs are missing or ambiguous.
4. Block issue publication unless approval is explicitly granted.

## Installation

1. Install upstream Spec-Kit CLI:
  - `bash scripts/install_spec_kit_deps.sh`
2. Verify CLI:
  - `specify --help`

`install_spec_kit_deps.sh` installs `uv` automatically if missing.

## Publish safety

- Use module CLI emit allowlists for repository targets.
- Keep emission audit logging enabled.

## Related files

- `AGENTS.md`
- `README.md`
- `contracts.md`
- `agent.schema.json`
- `workflow.schema.json`
- `src/agentskills/skills/spec_kit/script_entrypoints.py`
- `scripts/README.md`

## Script entrypoint

Use `python -m agentskills.skills.spec_kit plan` for deterministic dependency
ordering and parallel batch generation directly from skill input JSON.

Use `python -m agentskills.skills.spec_kit emit` to emit deterministic
`gh` issue-create commands and publish only when explicit approval is
provided.

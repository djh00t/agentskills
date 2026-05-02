# spec-kit skill

Deterministic wrapper skill for GitHub Spec-Kit.

## Purpose

Transform human specifications into dependency-aware execution plans and, after
approval, publish corresponding GitHub issues.

## Constraints

- Follow upstream Spec-Kit process and assets.
- Do not invent templates or process stages.
- Require clarification and approval checkpoints.

## Request Modes

- `new-feature`: use when planning net-new capabilities.
- `behavior-change`: use when changing already delivered behavior.

## Contracts

- `SKILL.md`
- `agent.schema.json`
- `workflow.schema.json`

## Scripts

- `python -m agentskills.skills.spec_kit plan`
- `python -m agentskills.skills.spec_kit emit`
- `scripts/install_spec_kit_deps.sh`
- `scripts/README.md`

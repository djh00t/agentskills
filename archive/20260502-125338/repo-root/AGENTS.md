# AGENTS

This repository is agent-first. Any agent operating here must follow this
contract.

## Core Rules

1. Do not invent workflow templates or process steps for `spec-kit`.
2. Use documented upstream Spec-Kit process and pinned assets only.
3. Ask humans for clarification when required inputs are ambiguous or missing.
4. Require explicit human approval before creating or updating GitHub issues.
5. Keep outputs deterministic for identical inputs.

## Determinism Policy

- Sort unordered collections before persistence or publication.
- Use stable IDs and fixed state transitions.
- Record decisions and approval outcomes as structured data.
- Do not publish if required approvals are absent.

## Agent Execution Model

- Validate input against stable schemas before processing.
- Build a dependency graph and derive execution order.
- Group independent tasks into deterministic parallel batches.
- Produce issue drafts from approved plans only.
- Publish through approved integration paths (`gh` CLI for v1).

## Safety and Change Controls

- Prefer dry-run mode for first execution in new environments.
- Never bypass approval checkpoints.
- Escalate uncertainty with a concrete question and options.
- Keep logs concise, structured, and auditable.

## Local Overrides

Skill-level `AGENTS.md` files may add stricter rules. They cannot relax this
root contract.

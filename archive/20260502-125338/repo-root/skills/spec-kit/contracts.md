# Contracts

The `spec-kit` skill uses stable JSON contracts to keep behavior predictable and
agent-friendly.

## Primary Schemas

- `agent.schema.json`: top-level request/response structure.
- `workflow.schema.json`: task dependency and planning model.

## Stability Policy

- Backward-compatible additions are allowed.
- Breaking changes require explicit version bump and migration notes.

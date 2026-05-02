# Agent Operations

## Startup Checklist

1. Read root `AGENTS.md`.
2. Read skill-local `AGENTS.md`.
3. Validate input against skill schema.
4. Enter dry-run mode unless explicitly instructed otherwise.

## Escalation Rules

- Escalate if required fields are missing.
- Escalate if dependency graph contains cycles.
- Escalate if approval is denied.

## Audit Trail

Record:

- clarification questions and responses
- approval decisions and approver identity
- generated issue payloads and publication results

# Contributing

## Development Flow

1. Add or update docs, features, and tests before behavior changes.
2. Keep contracts stable or versioned when changes are required.
3. Run `make check` before opening a pull request.

## Quality Gates

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=80`

## Agent-First Requirements

- Update root `AGENTS.md` and skill `AGENTS.md` when behavior changes.
- Keep schemas and examples synchronized.
- Keep human approval checkpoints explicit and test-covered.

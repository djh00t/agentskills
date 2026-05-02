# Standards

## Code Standards

- Python 3.11+
- Type hints required for public APIs
- Docstrings required for public modules, classes, and functions
- ASCII-safe punctuation only

## Repository Layout

This repo intentionally uses `src/agentskills` rather than
`src/mission_control`.

## Test Standards

- BDD feature files in `tests/features`.
- Unit tests in `tests/unit`.
- Integration tests in `tests/integration`.
- Coverage target is at least 80 percent for behavior changes.

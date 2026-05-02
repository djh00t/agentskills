---
name: quality-gates
description: Enforce linting, make check, and test coverage gates for changes.
compatibility: agents
metadata:
  language: python
  scope: quality
---
## What I do
- Require `make check` if available after each change.
- Run lint and tests after changes.
- Enforce unit test coverage of at least 80 percent for behavior changes.

## When to use me
- Use after any code change that affects behavior.
- Use before finalizing changes.

## Inputs I need
- Whether a Makefile and `check` target exist.
- Whether ruff and pytest-cov are installed.

## Steps
1) If a Makefile with `check` exists, run `make check`.
2) If lint tooling exists, run:
   - `python -m ruff check .`
   - `python -m ruff format --check .`
3) Run tests:
   - `python -m pytest`
4) Enforce coverage when pytest-cov is installed:
   - `python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80`
5) For a single test, use:
   - `python -m pytest tests/test_file.py::test_name`

## Acceptance checks
- `make check` passes (when available).
- Lint passes (when configured).
- Tests pass.
- Coverage is at least 80 percent for behavior changes.

## Failure modes and remediation
- No Makefile check target: add one or document the equivalent commands.
- Missing lint tools: add ruff to dev dependencies or document alternatives.
- Coverage below 80 percent: add tests or narrow the change.

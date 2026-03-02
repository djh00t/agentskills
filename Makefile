.PHONY: check skills-validate lint format-check test test-cov

check: skills-validate lint format-check test-cov

skills-validate:
	uvx --from skills-ref agentskills validate skills/spec-kit

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

test:
	uv run pytest

test-cov:
	uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=80

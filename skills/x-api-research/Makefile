UV ?= uv

.PHONY: help venv install lint format format-check test check clean

help:
	@echo "Targets:"
	@echo "  venv         Create skill-local .venv with uv"
	@echo "  install      Sync runtime and dev dependencies"
	@echo "  lint         Run ruff lint checks"
	@echo "  format       Auto-format with ruff"
	@echo "  format-check Verify formatting"
	@echo "  test         Run pytest"
	@echo "  check        Run format-check, lint, and tests"
	@echo "  clean        Remove virtualenv and test/lint caches"

venv:
	$(UV) venv .venv

install: venv
	$(UV) sync --group dev

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

format-check:
	$(UV) run ruff format --check .

test:
	$(UV) run pytest

check: format-check lint test

clean:
	rm -rf .venv .pytest_cache .ruff_cache .coverage __pycache__ tests/__pycache__ scripts/__pycache__

PYTHON ?= python3
PIP := $(PYTHON) -m pip
RUFF := $(PYTHON) -m ruff
PYTEST := $(PYTHON) -m pytest

.PHONY: help bootstrap-openclaw install lint format format-check test test-cov check clean

help:
	@echo "Targets:"
	@echo "  bootstrap-openclaw Prepare runtime in OpenClaw docker environment"
	@echo "  install      Install package with test tooling"
	@echo "  lint         Run ruff lint checks"
	@echo "  format       Auto-format code with ruff"
	@echo "  format-check Verify formatting"
	@echo "  test         Run test suite"
	@echo "  test-cov     Run tests with coverage >= 80%"
	@echo "  check        Run format-check, lint, and tests"
	@echo "  clean        Remove caches and build artifacts"

bootstrap-openclaw:
	bash scripts/bootstrap_openclaw.sh

install:
	$(PIP) install -e ".[test]"

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

format-check:
	$(RUFF) format --check .

test:
	$(PYTEST)

test-cov:
	$(PYTEST) --cov=src --cov-report=term-missing --cov-fail-under=80

check: format-check lint test

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov dist build *.egg-info
